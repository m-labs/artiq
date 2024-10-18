use core::cell::RefCell;
use urc::Urc;
use board_misoc::{csr, config};
#[cfg(has_drtio)]
use board_misoc::clock;
use board_artiq::drtio_routing;
use sched::Io;
use sched::Mutex;
use io::{Cursor, ProtoRead};
use session_proto::{DeviceMap, resolve_channel_name, set_device_map};
const ASYNC_ERROR_COLLISION: u8 = 1 << 0;
const ASYNC_ERROR_BUSY: u8 = 1 << 1;
const ASYNC_ERROR_SEQUENCE_ERROR: u8 = 1 << 2;

#[cfg(has_drtio)]
pub mod drtio {
    use super::*;
    use alloc::vec::Vec;
    use drtioaux;
    use proto_artiq::drtioaux_proto::{MASTER_PAYLOAD_MAX_SIZE, PayloadStatus};
    use rtio_dma::remote_dma;
    #[cfg(has_rtio_analyzer)]
    use analyzer::remote_analyzer::RemoteBuffer;
    use kernel::subkernel;
    use sched::Error as SchedError;

    #[derive(Fail, Debug)]
    pub enum Error {
        #[fail(display = "timed out")]
        Timeout,
        #[fail(display = "unexpected packet: {:?}", _0)]
        UnexpectedPacket(drtioaux::Packet),
        #[fail(display = "aux packet error")]
        AuxError,
        #[fail(display = "link down")]
        LinkDown,
        #[fail(display = "unexpected reply")]
        UnexpectedReply,
        #[fail(display = "error adding DMA trace on satellite #{}", _0)]
        DmaAddTraceFail(u8),
        #[fail(display = "error erasing DMA trace on satellite #{}", _0)]
        DmaEraseFail(u8),
        #[fail(display = "error playing back DMA trace on satellite #{}", _0)]
        DmaPlaybackFail(u8),
        #[fail(display = "error adding subkernel on satellite #{}", _0)]
        SubkernelAddFail(u8),
        #[fail(display = "error on subkernel run request on satellite #{}", _0)]
        SubkernelRunFail(u8),
        #[fail(display = "sched error: {}", _0)]
        SchedError(#[cause] SchedError),
    }

    impl From<SchedError> for Error {
        fn from(value: SchedError) -> Error {
            Error::SchedError(value)
        }
    }

    pub fn startup(io: &Io, aux_mutex: &Mutex,
            routing_table: &Urc<RefCell<drtio_routing::RoutingTable>>,
            up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>,
            ddma_mutex: &Mutex, subkernel_mutex: &Mutex) {
        let aux_mutex = aux_mutex.clone();
        let routing_table = routing_table.clone();
        let up_destinations = up_destinations.clone();
        let ddma_mutex = ddma_mutex.clone();
        let subkernel_mutex = subkernel_mutex.clone();
        io.spawn(16384, move |io| {
            let routing_table = routing_table.borrow();
            link_thread(io, &aux_mutex, &routing_table, &up_destinations, &ddma_mutex, &subkernel_mutex);
        });
    }

    fn link_rx_up(linkno: u8) -> bool {
        let linkno = linkno as usize;
        unsafe {
            (csr::DRTIO[linkno].rx_up_read)() == 1
        }
    }

    fn recv_aux_timeout(io: &Io, linkno: u8, timeout: u32) -> Result<drtioaux::Packet, Error> {
        let max_time = clock::get_ms() + timeout as u64;
        loop {
            if !link_rx_up(linkno) {
                return Err(Error::LinkDown);
            }
            if clock::get_ms() > max_time {
                return Err(Error::Timeout);
            }
            match drtioaux::recv(linkno) {
                Ok(Some(packet)) => return Ok(packet),
                Ok(None) => (),
                Err(_) => return Err(Error::AuxError)
            }
            io.relinquish()?;
        }
    }

    fn process_async_packets(io: &Io, ddma_mutex: &Mutex, subkernel_mutex: &Mutex, 
            routing_table: &drtio_routing::RoutingTable, linkno: u8, packet: &drtioaux::Packet
    ) -> bool {
        match packet {
            // packets to be consumed locally
            drtioaux::Packet::DmaPlaybackStatus { id, source, destination: 0, error, channel, timestamp } => {
                remote_dma::playback_done(io, ddma_mutex, *id, *source, *error, *channel, *timestamp);
                true
            },
            drtioaux::Packet::SubkernelFinished { id, destination: 0, with_exception, exception_src } => {
                subkernel::subkernel_finished(io, subkernel_mutex, *id, *with_exception, *exception_src);
                true
            },
            drtioaux::Packet::SubkernelMessage { id, source: from, destination: 0, status, length, data } => {
                subkernel::message_handle_incoming(io, subkernel_mutex, *id, *status, *length as usize, data);
                // acknowledge receiving part of the message
                drtioaux::send(linkno, 
                    &drtioaux::Packet::SubkernelMessageAck { destination: *from }
                ).unwrap();
                true
            },
            // (potentially) routable packets
            drtioaux::Packet::DmaAddTraceRequest      { destination, .. } |
                drtioaux::Packet::DmaAddTraceReply          { destination, .. } |
                drtioaux::Packet::DmaRemoveTraceRequest     { destination, .. } |
                drtioaux::Packet::DmaRemoveTraceReply       { destination, .. } |
                drtioaux::Packet::DmaPlaybackRequest        { destination, .. } |
                drtioaux::Packet::DmaPlaybackReply          { destination, .. } |
                drtioaux::Packet::SubkernelLoadRunRequest   { destination, .. } |
                drtioaux::Packet::SubkernelLoadRunReply     { destination, .. } |
                drtioaux::Packet::SubkernelMessage          { destination, .. } |
                drtioaux::Packet::SubkernelMessageAck       { destination, .. } |
                drtioaux::Packet::SubkernelExceptionRequest { destination, .. } |
                drtioaux::Packet::SubkernelException        { destination, .. } |
                drtioaux::Packet::DmaPlaybackStatus         { destination, .. } |
                drtioaux::Packet::SubkernelFinished         { destination, .. } => {
                if *destination == 0 {
                    false
                } else {
                    let dest_link = routing_table.0[*destination as usize][0] - 1;
                    if dest_link == linkno {
                        warn!("[LINK#{}] Re-routed packet would return to the same link, dropping: {:?}", linkno, packet);
                    } else {
                        drtioaux::send(dest_link, &packet).unwrap();
                    }
                    true
                }
            }
            _ => false
        }
    }

    pub fn aux_transact(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex,
            routing_table: &drtio_routing::RoutingTable, linkno: u8, request: &drtioaux::Packet
    ) -> Result<drtioaux::Packet, Error> {
        let _lock = aux_mutex.lock(io)?;
        drtioaux::send(linkno, request).unwrap();
        loop {
            let reply = recv_aux_timeout(io, linkno, 200)?;
            if !process_async_packets(io, ddma_mutex, subkernel_mutex, routing_table, linkno, &reply) {
                // returns none if it was an async packet
                return Ok(reply);
            }
        }
    }

    fn setup_transact(io: &Io, aux_mutex: &Mutex, linkno: u8, request: &drtioaux::Packet) -> Result<drtioaux::Packet, Error> {
        /* shorter aux_transact for setup purposes, no checking for async packets,
           as they should not be generated yet */
        let _lock = aux_mutex.lock(io)?;
        drtioaux::send(linkno, request).unwrap();
        recv_aux_timeout(io, linkno, 200)
    }

    pub fn clear_buffers(io: &Io, aux_mutex: &Mutex) {
        let _lock = aux_mutex.lock(io).unwrap();
        for linkno in 0..(csr::DRTIO.len() as u8) {
            if !link_rx_up(linkno) {
                continue;
            }
            let _ = recv_aux_timeout(io, linkno, 200);
        }
    }

    fn ping_remote(io: &Io, aux_mutex: &Mutex, linkno: u8) -> u32 {
        let mut count = 0;
        loop {
            if !link_rx_up(linkno) {
                return 0
            }
            count += 1;
            if count > 100 {
                return 0;
            }
            let reply = setup_transact(io, aux_mutex, linkno, &drtioaux::Packet::EchoRequest);
            match reply {
                Ok(drtioaux::Packet::EchoReply) => {
                    // make sure receive buffer is drained
                    let max_time = clock::get_ms() + 200;
                    loop {
                        if clock::get_ms() > max_time {
                            return count;
                        }
                        let _ = drtioaux::recv(linkno);
                        io.relinquish().unwrap();
                    }
                }
                _ => {}
            }
            io.relinquish().unwrap();
        }
    }

    fn sync_tsc(io: &Io, aux_mutex: &Mutex, linkno: u8) -> Result<(), Error> {
        let _lock = aux_mutex.lock(io).unwrap();

        unsafe {
            (csr::DRTIO[linkno as usize].set_time_write)(1);
            while (csr::DRTIO[linkno as usize].set_time_read)() == 1 {}
        }
        // TSCAck is the only aux packet that is sent spontaneously
        // by the satellite, in response to a TSC set on the RT link.
        let reply = recv_aux_timeout(io, linkno, 10000)?;
        if reply == drtioaux::Packet::TSCAck {
            return Ok(());
        } else {
            return Err(Error::UnexpectedReply);
        }
    }

    fn load_routing_table(io: &Io, aux_mutex: &Mutex,
        linkno: u8, routing_table: &drtio_routing::RoutingTable) -> Result<(), Error> {
        for i in 0..drtio_routing::DEST_COUNT {
            let reply = setup_transact(io, aux_mutex, linkno, &drtioaux::Packet::RoutingSetPath {
                destination: i as u8,
                hops: routing_table.0[i]
            })?;
            if reply != drtioaux::Packet::RoutingAck {
                return Err(Error::UnexpectedReply);
            }
        }
        Ok(())
    }

    fn set_rank(io: &Io, aux_mutex: &Mutex,
        linkno: u8, rank: u8) -> Result<(), Error> {
        let reply = setup_transact(io, aux_mutex, linkno,
            &drtioaux::Packet::RoutingSetRank {
                rank: rank
            })?;
        if reply != drtioaux::Packet::RoutingAck {
            return Err(Error::UnexpectedReply);
        }
        Ok(())
    }

    fn init_buffer_space(destination: u8, linkno: u8) {
        let linkno = linkno as usize;
        unsafe {
            (csr::DRTIO[linkno].destination_write)(destination);
            (csr::DRTIO[linkno].force_destination_write)(1);
            (csr::DRTIO[linkno].o_get_buffer_space_write)(1);
            while (csr::DRTIO[linkno].o_wait_read)() == 1 {}
            info!("[DEST#{}] buffer space is {}",
                destination, (csr::DRTIO[linkno].o_dbg_buffer_space_read)());
            (csr::DRTIO[linkno].force_destination_write)(0);
        }
    }

    fn process_unsolicited_aux(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex, 
        routing_table: &drtio_routing::RoutingTable, linkno: u8) {
        let _lock = aux_mutex.lock(io).unwrap();
        loop {
            match drtioaux::recv(linkno) {
                Ok(Some(packet)) => {
                    if !process_async_packets(&io, ddma_mutex, subkernel_mutex, routing_table, linkno, &packet) {
                        warn!("[LINK#{}] unsolicited aux packet: {:?}", linkno, packet);
                    }
                },
                Ok(None) => return,
                Err(_) => { warn!("[LINK#{}] aux packet error", linkno); return }
            }
        }
    }

    fn process_local_errors(linkno: u8) {
        let errors;
        let linkidx = linkno as usize;
        unsafe {
            errors = (csr::DRTIO[linkidx].protocol_error_read)();
            (csr::DRTIO[linkidx].protocol_error_write)(errors);
        }
        if errors != 0 {
            error!("[LINK#{}] error(s) found (0x{:02x}):", linkno, errors);
            if errors & 1 != 0 {
                error!("[LINK#{}] received packet of an unknown type", linkno);
            }
            if errors & 2 != 0 {
                error!("[LINK#{}] received truncated packet", linkno);
            }
            if errors & 4 != 0 {
                error!("[LINK#{}] timeout attempting to get remote buffer space", linkno);
            }
        }
    }

    fn destination_set_up(routing_table: &drtio_routing::RoutingTable,
            up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>,
            destination: u8, up: bool) {
        let mut up_destinations = up_destinations.borrow_mut();
        up_destinations[destination as usize] = up;
        if up {
            drtio_routing::interconnect_enable(routing_table, 0, destination);
            info!("[DEST#{}] destination is up", destination);
        } else {
            drtio_routing::interconnect_disable(destination);
            info!("[DEST#{}] destination is down", destination);
        }
    }

    fn destination_up(up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>, destination: u8) -> bool {
        let up_destinations = up_destinations.borrow();
        up_destinations[destination as usize]
    }

    fn destination_survey(io: &Io, aux_mutex: &Mutex, routing_table: &drtio_routing::RoutingTable,
            up_links: &[bool],
            up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>,
            ddma_mutex: &Mutex, subkernel_mutex: &Mutex) {
        for destination in 0..drtio_routing::DEST_COUNT {
            let hop = routing_table.0[destination][0];
            let destination = destination as u8;

            if hop == 0 {
                /* local RTIO */
                if !destination_up(up_destinations, destination) {
                    destination_set_up(routing_table, up_destinations, destination, true);
                }
            } else if hop as usize <= csr::DRTIO.len() {
                let linkno = hop - 1;
                if destination_up(up_destinations, destination) {
                    if up_links[linkno as usize] {
                        let reply = aux_transact(io, aux_mutex,
                             ddma_mutex, subkernel_mutex, routing_table, linkno,
                            &drtioaux::Packet::DestinationStatusRequest {
                                destination: destination
                            });
                        if let Ok(reply) = reply {
                            match reply {
                                drtioaux::Packet::DestinationDownReply => {
                                    destination_set_up(routing_table, up_destinations, destination, false);
                                    remote_dma::destination_changed(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, destination, false);
                                    subkernel::destination_changed(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, destination, false);
                                }
                                drtioaux::Packet::DestinationOkReply => (),
                                drtioaux::Packet::DestinationSequenceErrorReply { channel } => {
                                    error!("[DEST#{}] RTIO sequence error involving channel 0x{:04x}:{}", destination, channel, resolve_channel_name(channel as u32));
                                    unsafe { SEEN_ASYNC_ERRORS |= ASYNC_ERROR_SEQUENCE_ERROR };
                                }
                                drtioaux::Packet::DestinationCollisionReply { channel } => {
                                    error!("[DEST#{}] RTIO collision involving channel 0x{:04x}:{}", destination, channel, resolve_channel_name(channel as u32));
                                    unsafe { SEEN_ASYNC_ERRORS |= ASYNC_ERROR_COLLISION };
                                }
                                drtioaux::Packet::DestinationBusyReply { channel } => {
                                    error!("[DEST#{}] RTIO busy error involving channel 0x{:04x}:{}", destination, channel, resolve_channel_name(channel as u32));
                                    unsafe { SEEN_ASYNC_ERRORS |= ASYNC_ERROR_BUSY };
                                }
                                packet => error!("[DEST#{}] received unexpected aux packet: {:?}", destination, packet),
                                
                            }
                        } else { 
                            error!("[DEST#{}] communication failed ({:?})", destination, reply.unwrap_err()); 
                        }
                    } else {
                        destination_set_up(routing_table, up_destinations, destination, false);
                        remote_dma::destination_changed(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, destination, false);
                        subkernel::destination_changed(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, destination, false);
                    }
                } else {
                    if up_links[linkno as usize] {
                        let reply = aux_transact(io, aux_mutex, ddma_mutex,
                            subkernel_mutex, routing_table, linkno,
                            &drtioaux::Packet::DestinationStatusRequest {
                                destination: destination
                            });
                        match reply {
                            Ok(drtioaux::Packet::DestinationDownReply) => (),
                            Ok(drtioaux::Packet::DestinationOkReply) => {
                                destination_set_up(routing_table, up_destinations, destination, true);
                                init_buffer_space(destination as u8, linkno);
                                remote_dma::destination_changed(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, destination, true);
                                subkernel::destination_changed(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, destination, true);
                            },
                            Ok(packet) => error!("[DEST#{}] received unexpected aux packet: {:?}", destination, packet),
                            Err(e) => error!("[DEST#{}] communication failed ({:?})", destination, e)
                        }
                    }
                }
            }
        }
    }

    pub fn link_thread(io: Io, aux_mutex: &Mutex,
            routing_table: &drtio_routing::RoutingTable,
            up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>,
            ddma_mutex: &Mutex, subkernel_mutex: &Mutex) {
        let mut up_links = [false; csr::DRTIO.len()];
        loop {
            for linkno in 0..csr::DRTIO.len() {
                let linkno = linkno as u8;
                if up_links[linkno as usize] {
                    /* link was previously up */
                    if link_rx_up(linkno) {
                        process_unsolicited_aux(&io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, linkno);
                        process_local_errors(linkno);
                    } else {
                        info!("[LINK#{}] link is down", linkno);
                        up_links[linkno as usize] = false;
                    }
                } else {
                    /* link was previously down */
                    if link_rx_up(linkno) {
                        info!("[LINK#{}] link RX became up, pinging", linkno);
                        let ping_count = ping_remote(&io, aux_mutex, linkno);
                        if ping_count > 0 {
                            info!("[LINK#{}] remote replied after {} packets", linkno, ping_count);
                            up_links[linkno as usize] = true;
                            if let Err(e) = sync_tsc(&io, aux_mutex, linkno) {
                                error!("[LINK#{}] failed to sync TSC ({:?})", linkno, e);
                            }
                            if let Err(e) = load_routing_table(&io, aux_mutex, linkno, routing_table) {
                                error!("[LINK#{}] failed to load routing table ({:?})", linkno, e);
                            }
                            if let Err(e) = set_rank(&io, aux_mutex, linkno, 1) {
                                error!("[LINK#{}] failed to set rank ({:?})", linkno, e);
                            }
                            info!("[LINK#{}] link initialization completed", linkno);
                        } else {
                            error!("[LINK#{}] ping failed", linkno);
                        }
                    }
                }
            }
            destination_survey(&io, aux_mutex, routing_table, &up_links, up_destinations, ddma_mutex, subkernel_mutex);
            io.sleep(200).unwrap();
        }
    }

    pub fn reset(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex, routing_table: &drtio_routing::RoutingTable) {
        for linkno in 0..csr::DRTIO.len() {
            unsafe {
                (csr::DRTIO[linkno].reset_write)(1);
            }
        }
        io.sleep(1).unwrap();
        for linkno in 0..csr::DRTIO.len() {
            unsafe {
                (csr::DRTIO[linkno].reset_write)(0);
            }
        }

        for linkno in 0..csr::DRTIO.len() {
            let linkno = linkno as u8;
            if link_rx_up(linkno) {
                let reply = aux_transact(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, linkno,
                    &drtioaux::Packet::ResetRequest);
                match reply {
                    Ok(drtioaux::Packet::ResetAck) => (),
                    Ok(_) => error!("[LINK#{}] reset failed, received unexpected aux packet", linkno),
                    Err(e) => error!("[LINK#{}] reset failed, aux packet error ({:?})", linkno, e)
                }
            }
        }
    }

    fn partition_data<F>(data: &[u8], send_f: F) -> Result<(), Error>
            where F: Fn(&[u8; MASTER_PAYLOAD_MAX_SIZE], PayloadStatus, usize) -> Result<(), Error> {
            let mut i = 0;
            while i < data.len() {
                let mut slice: [u8; MASTER_PAYLOAD_MAX_SIZE] = [0; MASTER_PAYLOAD_MAX_SIZE];
                let len: usize = if i + MASTER_PAYLOAD_MAX_SIZE < data.len() { MASTER_PAYLOAD_MAX_SIZE } else { data.len() - i } as usize;
                let first = i == 0;
                let last = i + len == data.len();
                let status = PayloadStatus::from_status(first, last);
                slice[..len].clone_from_slice(&data[i..i+len]);
                i += len;
                send_f(&slice, status, len)?;
            }
            Ok(())
        }

    pub fn ddma_upload_trace(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex,
            routing_table: &drtio_routing::RoutingTable, id: u32, destination: u8, trace: &[u8]
    ) -> Result<(), Error> {
        let linkno = routing_table.0[destination as usize][0] - 1;
        partition_data(trace, |slice, status, len: usize| {
            let reply = aux_transact(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, linkno,
                &drtioaux::Packet::DmaAddTraceRequest {
                    id: id, source: 0, destination: destination, status: status, length: len as u16, trace: *slice})?;
            match reply {
                drtioaux::Packet::DmaAddTraceReply { destination: 0, succeeded: true, .. } => Ok(()),
                drtioaux::Packet::DmaAddTraceReply { destination: 0, succeeded: false, .. } => Err(Error::DmaAddTraceFail(destination)),
                packet => Err(Error::UnexpectedPacket(packet)),
            }
        })
    }

    pub fn ddma_send_erase(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex,
            routing_table: &drtio_routing::RoutingTable, id: u32, destination: u8) -> Result<(), Error> {
        let linkno = routing_table.0[destination as usize][0] - 1;
        let reply = aux_transact(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, linkno, 
            &drtioaux::Packet::DmaRemoveTraceRequest { id: id, source: 0, destination: destination })?;
        match reply {
            drtioaux::Packet::DmaRemoveTraceReply { destination: 0, succeeded: true } => Ok(()),
            drtioaux::Packet::DmaRemoveTraceReply { destination: 0, succeeded: false } => Err(Error::DmaEraseFail(destination)),
            packet => Err(Error::UnexpectedPacket(packet)),
        }
    }

    pub fn ddma_send_playback(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex,
            routing_table: &drtio_routing::RoutingTable, id: u32, destination: u8, timestamp: u64) -> Result<(), Error> {
        let linkno = routing_table.0[destination as usize][0] - 1;
        let reply = aux_transact(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, linkno, 
            &drtioaux::Packet::DmaPlaybackRequest{ id: id, source: 0, destination: destination, timestamp: timestamp })?;
        match reply {
            drtioaux::Packet::DmaPlaybackReply { destination: 0, succeeded: true } => Ok(()),
            drtioaux::Packet::DmaPlaybackReply { destination: 0, succeeded: false } =>
                    Err(Error::DmaPlaybackFail(destination)),
            packet => Err(Error::UnexpectedPacket(packet)),
        }
    }

    #[cfg(has_rtio_analyzer)]
    fn analyzer_get_data(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex,
        routing_table: &drtio_routing::RoutingTable, destination: u8) -> Result<RemoteBuffer, Error> {
        let linkno = routing_table.0[destination as usize][0] - 1;
        let reply = aux_transact(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, linkno, 
            &drtioaux::Packet::AnalyzerHeaderRequest { destination: destination })?;
        let (sent, total, overflow) = match reply {
            drtioaux::Packet::AnalyzerHeader { sent_bytes, total_byte_count, overflow_occurred } => 
                (sent_bytes, total_byte_count, overflow_occurred),
            packet => return Err(Error::UnexpectedPacket(packet)),
        };

        let mut remote_data: Vec<u8> = Vec::new();
        if sent > 0 {
            let mut last_packet = false;
            while !last_packet {
                let reply = aux_transact(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, linkno, 
                    &drtioaux::Packet::AnalyzerDataRequest { destination: destination })?;
                match reply {
                    drtioaux::Packet::AnalyzerData { last, length, data } => { 
                        last_packet = last;
                        remote_data.extend(&data[0..length as usize]);
                    },
                    packet => return Err(Error::UnexpectedPacket(packet)),
                }
            }
        }

        Ok(RemoteBuffer {
            sent_bytes: sent,
            total_byte_count: total,
            overflow_occurred: overflow,
            data: remote_data
        })
    }

    #[cfg(has_rtio_analyzer)]
    pub fn analyzer_query(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex,
        routing_table: &drtio_routing::RoutingTable, up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>
    ) -> Result<Vec<RemoteBuffer>, Error> {
        let mut remote_buffers: Vec<RemoteBuffer> = Vec::new();
        for i in 1..drtio_routing::DEST_COUNT {
            if destination_up(up_destinations, i as u8) {
                remote_buffers.push(analyzer_get_data(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, i as u8)?);
            }
        }
        Ok(remote_buffers)
    }

    pub fn subkernel_upload(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex,
            routing_table: &drtio_routing::RoutingTable, id: u32, destination: u8, data: &Vec<u8>) -> Result<(), Error> {
        let linkno = routing_table.0[destination as usize][0] - 1;
        partition_data(data, |slice, status, len: usize| {
            let reply = aux_transact(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, linkno, 
                &drtioaux::Packet::SubkernelAddDataRequest {
                    id: id, destination: destination, status: status, length: len as u16, data: *slice})?;
            match reply {
                drtioaux::Packet::SubkernelAddDataReply { succeeded: true } => Ok(()),
                drtioaux::Packet::SubkernelAddDataReply { succeeded: false } =>  
                    Err(Error::SubkernelAddFail(destination)),
                    packet => Err(Error::UnexpectedPacket(packet)),
            }
        })
    }

    pub fn subkernel_load(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex, 
            routing_table: &drtio_routing::RoutingTable, id: u32, destination: u8, run: bool, timestamp: u64
        ) -> Result<(), Error> {
        let linkno = routing_table.0[destination as usize][0] - 1;
        let reply = aux_transact(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, linkno, 
            &drtioaux::Packet::SubkernelLoadRunRequest{ 
                id: id, source: 0, destination: destination,
                run: run, timestamp: timestamp
            })?;
        match reply {
            drtioaux::Packet::SubkernelLoadRunReply { destination: 0, succeeded: true } => Ok(()),
            drtioaux::Packet::SubkernelLoadRunReply { destination: 0, succeeded: false } =>
                    Err(Error::SubkernelRunFail(destination)),
                packet => Err(Error::UnexpectedPacket(packet)),
        }
    }

    pub fn subkernel_retrieve_exception(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex,
        routing_table: &drtio_routing::RoutingTable, destination: u8
    ) -> Result<Vec<u8>, Error> {
        let linkno = routing_table.0[destination as usize][0] - 1;
        let mut remote_data: Vec<u8> = Vec::new();
        loop {
            let reply = aux_transact(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, linkno, 
                &drtioaux::Packet::SubkernelExceptionRequest { source: 0, destination: destination })?;
            match reply {
                drtioaux::Packet::SubkernelException { destination: 0, last, length, data } => { 
                    remote_data.extend(&data[0..length as usize]);
                    if last {
                        return Ok(remote_data);
                    }
                },
                packet => return Err(Error::UnexpectedPacket(packet)),
            }
        }
    }

    pub fn subkernel_send_message(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex,
        routing_table: &drtio_routing::RoutingTable, id: u32, destination: u8, message: &[u8]
    ) -> Result<(), Error> {
        let linkno = routing_table.0[destination as usize][0] - 1;
        partition_data(message, |slice, status, len: usize| {
            let reply = aux_transact(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, linkno, 
                &drtioaux::Packet::SubkernelMessage {
                    source: 0, destination: destination,
                    id: id, status: status, length: len as u16, data: *slice})?;
            match reply {
                drtioaux::Packet::SubkernelMessageAck { .. } => Ok(()),
                packet => Err(Error::UnexpectedPacket(packet)),
            }
        })
    }
}

#[cfg(not(has_drtio))]
pub mod drtio {
    use super::*;

    pub fn startup(_io: &Io, _aux_mutex: &Mutex,
        _routing_table: &Urc<RefCell<drtio_routing::RoutingTable>>,
        _up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>,
        _ddma_mutex: &Mutex, _subkernel_mutex: &Mutex) {}
    pub fn reset(_io: &Io, _aux_mutex: &Mutex, _ddma_mutex: &Mutex, _subkernel_mutex: &Mutex, _routing_table: &drtio_routing::RoutingTable) {}
}

static mut SEEN_ASYNC_ERRORS: u8 = 0;

pub unsafe fn get_async_errors() -> u8 {
    let errors = SEEN_ASYNC_ERRORS;
    SEEN_ASYNC_ERRORS = 0;
    errors
}

fn async_error_thread(io: Io) {
    loop {
        unsafe {
            io.until(|| csr::rtio_core::async_error_read() != 0).unwrap();
            let errors = csr::rtio_core::async_error_read();
            if errors & ASYNC_ERROR_COLLISION != 0 {
                let channel = csr::rtio_core::collision_channel_read();
                error!("RTIO collision involving channel 0x{:04x}:{}", channel, resolve_channel_name(channel as u32));
            }
            if errors & ASYNC_ERROR_BUSY != 0 {
                let channel = csr::rtio_core::busy_channel_read();
                error!("RTIO busy error involving channel 0x{:04x}:{}", channel, resolve_channel_name(channel as u32));
            }
            if errors & ASYNC_ERROR_SEQUENCE_ERROR != 0 {
                let channel = csr::rtio_core::sequence_error_channel_read();
                error!("RTIO sequence error involving channel 0x{:04x}:{}", channel, resolve_channel_name(channel as u32));
            }
            SEEN_ASYNC_ERRORS = errors;
            csr::rtio_core::async_error_write(errors);
        }
    }
}

fn read_device_map() -> DeviceMap {
    let mut device_map: DeviceMap = DeviceMap::new();
    config::read("device_map", |value: Result<&[u8], config::Error>| {
        let mut bytes = match value {
            Ok(val) => if val.len() > 0 { Cursor::new(val) } else {
                warn!("device map not found in config, device names will not be available in RTIO error messages");
                return;
            },
            Err(err) => {
                warn!("error reading device map ({}), device names will not be available in RTIO error messages", err);
                return;
            }
        };
        let size = bytes.read_u32().unwrap();
        for _ in 0..size {
            let channel = bytes.read_u32().unwrap();
            let device_name= bytes.read_string().unwrap();
            if let Some(old_entry) = device_map.insert(channel, device_name.clone()) {
                warn!("conflicting device map entries for RTIO channel {}: '{}' and '{}'",
                       channel, old_entry, device_name);
            }
        }
    });
    device_map
}

fn toggle_sed_spread(val: u8) {
    unsafe { csr::rtio_core::sed_spread_enable_write(val); }
}

fn setup_sed_spread() {
    config::read_str("sed_spread_enable", |r| {
        match r {
            Ok("1") => { info!("SED spreading enabled"); toggle_sed_spread(1); },
            Ok("0") => { info!("SED spreading disabled"); toggle_sed_spread(0); },
            Ok(_) => { 
                warn!("sed_spread_enable value not supported (only 1, 0 allowed), disabling by default");
                toggle_sed_spread(0);
            },
            Err(_) => { info!("SED spreading disabled by default"); toggle_sed_spread(0) },
        }
    });
}

pub fn startup(io: &Io, aux_mutex: &Mutex,
        routing_table: &Urc<RefCell<drtio_routing::RoutingTable>>,
        up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>,
        ddma_mutex: &Mutex, subkernel_mutex: &Mutex) {
    set_device_map(read_device_map());
    setup_sed_spread();
    drtio::startup(io, aux_mutex, routing_table, up_destinations, ddma_mutex, subkernel_mutex);
    unsafe {
        csr::rtio_core::reset_phy_write(1);
    }
    io.spawn(4096, async_error_thread);
}

pub fn reset(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex,
    routing_table: &drtio_routing::RoutingTable) {
    unsafe {
        csr::rtio_core::reset_write(1);
    }
    drtio::reset(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table)
}
