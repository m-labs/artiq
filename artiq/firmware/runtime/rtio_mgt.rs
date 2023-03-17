use alloc::collections::BTreeMap;
use alloc::string::String;
use alloc::vec::Vec;
use core::cell::RefCell;
use urc::Urc;
use board_misoc::{csr, config};
#[cfg(has_drtio)]
use board_misoc::clock;
use board_artiq::drtio_routing;
use sched::Io;
use sched::Mutex;
use rtio_dma::RemoteManager;
use io::{Cursor, ProtoRead};
const ASYNC_ERROR_COLLISION: u8 = 1 << 0;
const ASYNC_ERROR_BUSY: u8 = 1 << 1;
const ASYNC_ERROR_SEQUENCE_ERROR: u8 = 1 << 2;

static mut RTIO_DEVICE_MAP: BTreeMap<u32, String> = BTreeMap::new();

#[cfg(has_drtio)]
pub mod drtio {
    use super::*;
    use drtioaux;
    use proto_artiq::drtioaux_proto::DMA_TRACE_MAX_SIZE;
    use rtio_dma::RemoteState;

    pub fn startup(io: &Io, aux_mutex: &Mutex,
            routing_table: &Urc<RefCell<drtio_routing::RoutingTable>>,
            up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>,
            remote_mgr: &Urc<RefCell<RemoteManager>>) {
        let aux_mutex = aux_mutex.clone();
        let routing_table = routing_table.clone();
        let up_destinations = up_destinations.clone();
        let remote_mgr = remote_mgr.clone();
        io.spawn(4096, move |io| {
            let routing_table = routing_table.borrow();
            link_thread(io, &aux_mutex, &routing_table, &up_destinations, &remote_mgr);
        });
    }

    fn link_rx_up(linkno: u8) -> bool {
        let linkno = linkno as usize;
        unsafe {
            (csr::DRTIO[linkno].rx_up_read)() == 1
        }
    }

    fn recv_aux_timeout(io: &Io, linkno: u8, timeout: u32) -> Result<drtioaux::Packet, &'static str> {
        let max_time = clock::get_ms() + timeout as u64;
        loop {
            if !link_rx_up(linkno) {
                return Err("link went down");
            }
            if clock::get_ms() > max_time {
                return Err("timeout");
            }
            match drtioaux::recv(linkno) {
                Ok(Some(packet)) => return Ok(packet),
                Ok(None) => (),
                Err(_) => return Err("aux packet error")
            }
            io.relinquish().unwrap();
        }
    }

    pub fn aux_transact(io: &Io, aux_mutex: &Mutex,
            linkno: u8, request: &drtioaux::Packet) -> Result<drtioaux::Packet, &'static str> {
        let _lock = aux_mutex.lock(io).unwrap();
        drtioaux::send(linkno, request).unwrap();
        recv_aux_timeout(io, linkno, 200)
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
            let reply = aux_transact(io, aux_mutex, linkno, &drtioaux::Packet::EchoRequest);
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

    fn sync_tsc(io: &Io, aux_mutex: &Mutex, linkno: u8) -> Result<(), &'static str> {
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
            return Err("unexpected reply");
        }
    }

    fn load_routing_table(io: &Io, aux_mutex: &Mutex, linkno: u8, routing_table: &drtio_routing::RoutingTable)
            -> Result<(), &'static str> {
        for i in 0..drtio_routing::DEST_COUNT {
            let reply = aux_transact(io, aux_mutex, linkno, &drtioaux::Packet::RoutingSetPath {
                destination: i as u8,
                hops: routing_table.0[i]
            })?;
            if reply != drtioaux::Packet::RoutingAck {
                return Err("unexpected reply");
            }
        }
        Ok(())
    }

    fn set_rank(io: &Io, aux_mutex: &Mutex, linkno: u8, rank: u8) -> Result<(), &'static str> {
        let reply = aux_transact(io, aux_mutex, linkno, &drtioaux::Packet::RoutingSetRank {
            rank: rank
        })?;
        if reply != drtioaux::Packet::RoutingAck {
            return Err("unexpected reply");
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

    fn process_unsolicited_aux(io: &Io, aux_mutex: &Mutex, linkno: u8, remote_mgr: &Urc<RefCell<RemoteManager>>) {
        let _lock = aux_mutex.lock(io).unwrap();
        match drtioaux::recv(linkno) {
            Ok(Some(drtioaux::Packet::DmaPlaybackStatus { id: reply_id, destination: dest, error, channel, timestamp })) => {
                let remote_mgr = remote_mgr.borrow();
                remote_mgr.change_state(reply_id, dest, RemoteState::PlaybackEnded { error: error, channel: channel, timestamp: timestamp });
            }
            Ok(Some(packet)) => warn!("[LINK#{}] unsolicited aux packet: {:?}", linkno, packet),
            Ok(None) => (),
            Err(_) => warn!("[LINK#{}] aux packet error", linkno)
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
            remote_mgr: &Urc<RefCell<RemoteManager>>) {
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
                        let reply = aux_transact(io, aux_mutex, linkno, &drtioaux::Packet::DestinationStatusRequest {
                            destination: destination
                        });
                        match reply {
                            Ok(drtioaux::Packet::DestinationDownReply) => {
                                destination_set_up(routing_table, up_destinations, destination, false);
                                dma_update_up(io, aux_mutex, routing_table, remote_mgr, destination, false);
                            }
                            Ok(drtioaux::Packet::DestinationOkReply) => (),
                            Ok(drtioaux::Packet::DestinationSequenceErrorReply { channel }) => {
                                error!("[DEST#{}] RTIO sequence error involving channel 0x{:04x}:{}", destination, channel, resolve_channel_name(channel as u32));
                                unsafe { SEEN_ASYNC_ERRORS |= ASYNC_ERROR_SEQUENCE_ERROR };
                            }
                            Ok(drtioaux::Packet::DestinationCollisionReply { channel }) => {
                                error!("[DEST#{}] RTIO collision involving channel 0x{:04x}:{}", destination, channel, resolve_channel_name(channel as u32));
                                unsafe { SEEN_ASYNC_ERRORS |= ASYNC_ERROR_COLLISION };
                            }
                            Ok(drtioaux::Packet::DestinationBusyReply { channel }) => {
                                error!("[DEST#{}] RTIO busy error involving channel 0x{:04x}:{}", destination, channel, resolve_channel_name(channel as u32));
                                unsafe { SEEN_ASYNC_ERRORS |= ASYNC_ERROR_BUSY };
                            }
                            Ok(packet) => error!("[DEST#{}] received unexpected aux packet: {:?}", destination, packet),
                            Err(e) => error!("[DEST#{}] communication failed ({})", destination, e)
                        }
                    } else {
                        destination_set_up(routing_table, up_destinations, destination, false);
                        dma_update_up(io, aux_mutex, routing_table, remote_mgr, destination, false);
                    }
                } else {
                    if up_links[linkno as usize] {
                        let reply = aux_transact(io, aux_mutex, linkno, &drtioaux::Packet::DestinationStatusRequest {
                            destination: destination
                        });
                        match reply {
                            Ok(drtioaux::Packet::DestinationDownReply) => (),
                            Ok(drtioaux::Packet::DestinationOkReply) => {
                                destination_set_up(routing_table, up_destinations, destination, true);
                                init_buffer_space(destination as u8, linkno);
                                dma_update_up(io, aux_mutex, routing_table, remote_mgr, destination, true);
                            },
                            Ok(packet) => error!("[DEST#{}] received unexpected aux packet: {:?}", destination, packet),
                            Err(e) => error!("[DEST#{}] communication failed ({})", destination, e)
                        }
                    }
                }
            }
        }
    }

    pub fn link_thread(io: Io, aux_mutex: &Mutex,
            routing_table: &drtio_routing::RoutingTable,
            up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>,
            remote_mgr: &Urc<RefCell<RemoteManager>>) {
        let mut up_links = [false; csr::DRTIO.len()];
        loop {
            for linkno in 0..csr::DRTIO.len() {
                let linkno = linkno as u8;
                if up_links[linkno as usize] {
                    /* link was previously up */
                    if link_rx_up(linkno) {
                        process_unsolicited_aux(&io, aux_mutex, linkno, remote_mgr);
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
                                error!("[LINK#{}] failed to sync TSC ({})", linkno, e);
                            }
                            if let Err(e) = load_routing_table(&io, aux_mutex, linkno, routing_table) {
                                error!("[LINK#{}] failed to load routing table ({})", linkno, e);
                            }
                            if let Err(e) = set_rank(&io, aux_mutex, linkno, 1) {
                                error!("[LINK#{}] failed to set rank ({})", linkno, e);
                            }
                            info!("[LINK#{}] link initialization completed", linkno);
                        } else {
                            error!("[LINK#{}] ping failed", linkno);
                        }
                    }
                }
            }
            destination_survey(&io, aux_mutex, routing_table, &up_links, up_destinations, remote_mgr);
            io.sleep(200).unwrap();
        }
    }

    pub fn reset(io: &Io, aux_mutex: &Mutex) {
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
                let reply = aux_transact(io, aux_mutex, linkno,
                    &drtioaux::Packet::ResetRequest);
                match reply {
                    Ok(drtioaux::Packet::ResetAck) => (),
                    Ok(_) => error!("[LINK#{}] reset failed, received unexpected aux packet", linkno),
                    Err(e) => error!("[LINK#{}] reset failed, aux packet error ({})", linkno, e)
                }
            }
        }
    }

    fn dma_update_up(io: &Io, aux_mutex: &Mutex, 
        routing_table: &drtio_routing::RoutingTable, 
        remote_mgr: &Urc<RefCell<RemoteManager>>, 
        destination: u8, up: bool) {
        //update status after link is lost or restored
        //also re-send the trace if needed
        let mut remote_mgr = remote_mgr.borrow_mut();
        let destination_traces = remote_mgr.get_traces_for_destination(destination);
        for (id, mut trace) in destination_traces {
            if up {
                match dma_dispatch(io, aux_mutex, routing_table, id, destination, trace.get_trace())
                {
                    Ok(_) => trace.update_state(RemoteState::Loaded),
                    Err(e) => error!("Error adding DMA trace on destination {}: {}", destination, e)
                }
            } else {
                trace.update_state(RemoteState::NotLoaded);
            }
        }

    }

    fn dma_dispatch(io: &Io, aux_mutex: &Mutex, 
        routing_table: &drtio_routing::RoutingTable,
        id: u32, destination: u8, trace: &Vec<u8>) -> Result<(), &'static str> {
        let linkno = routing_table.0[destination as usize][0];
        let mut i = 0;
        while i <= trace.len() {
            let mut trace_slice: [u8; DMA_TRACE_MAX_SIZE] = [0; DMA_TRACE_MAX_SIZE];
            let len: usize = if i + DMA_TRACE_MAX_SIZE < trace.len() { DMA_TRACE_MAX_SIZE } else { trace.len() - i } as usize;
            let last = i + len == trace.len();
            i += len;
            trace_slice.clone_from_slice(&trace[i..i+len]);
            let reply = aux_transact(io, aux_mutex, linkno, 
                &drtioaux::Packet::DmaAddTraceRequest {
                    id: id, destination: destination, last: last, length: len as u16, trace: trace_slice});
            match reply {
                Ok(drtioaux::Packet::DmaAddTraceReply { succeeded: succeeded }) => { 
                    if !succeeded { return Err("error on satellite"); }
                    },
                Ok(_) => { return Err("adding DMA trace failed, unexpected aux packet"); },
                Err(_) => { return Err("adding DMA trace failed, aux error"); }
            }
        }
        Ok(())
    }

    pub fn dma_send_traces(io: &Io, aux_mutex: &Mutex, 
        routing_table: &drtio_routing::RoutingTable, 
        remote_mgr: &Urc<RefCell<RemoteManager>>, id: u32) {
        let mut remote_mgr = remote_mgr.borrow_mut();
        if let Some(traces) = remote_mgr.get_traces(id) {
            for (destination, trace) in traces {
                match dma_dispatch(io, aux_mutex, routing_table, id, *destination, trace.get_trace())
                {
                    Ok(_) => trace.update_state(RemoteState::Loaded),
                    Err(e) => error!("Error adding DMA trace on destination {}: {}", destination, e)
                }
            }
        }
    }

    pub fn dma_erase(io: &Io, aux_mutex: &Mutex, 
        routing_table: &drtio_routing::RoutingTable, 
        remote_mgr: &Urc<RefCell<RemoteManager>>,
        id: u32) {
        let mut remote_mgr = remote_mgr.borrow_mut();
        if let Some(destinations) = remote_mgr.get_destinations(id) {
            for destination in destinations {
                let linkno = routing_table.0[destination as usize][0];
                let reply = aux_transact(io, aux_mutex, linkno, 
                    &drtioaux::Packet::DmaRemoveTraceRequest { id: id, destination: destination });
                match reply {
                    Ok(drtioaux::Packet::DmaRemoveTraceReply { succeeded: succeeded }) => {
                        if !succeeded { 
                            error!("error erasing DMA trace on satellite for destination {}", destination); 
                        }
                    },
                    Ok(_) => error!("adding trace failed, unexpected aux packet"),
                    Err(e) => error!("erasing trace failed, aux error {}", e)
                }
            }
        }
    }

    pub fn dma_playback(io: &Io, aux_mutex: &Mutex, 
        routing_table: &drtio_routing::RoutingTable, 
        remote_mgr: &Urc<RefCell<RemoteManager>>,
        id: u32, timestamp: u64) {
        let mut remote_mgr = remote_mgr.borrow_mut();
        if let Some(destinations) = remote_mgr.get_traces(id) {
            for (destination, mut trace) in destinations {
                let state = trace.get_state();
                if *state != RemoteState::Loaded {
                    error!("Destination {} not ready for DMA, state: {:?}", destination, state);
                    continue;
                }
                let linkno = routing_table.0[*destination as usize][0];
                {
                    let _lock = aux_mutex.lock(io).unwrap();
                    drtioaux::send(linkno, &drtioaux::Packet::DmaPlaybackRequest{
                            id: id, destination: * destination, timestamp: timestamp }).unwrap();
                    loop {
                        let reply = recv_aux_timeout(io, linkno, 200);
                        match reply {
                            Ok(drtioaux::Packet::DmaPlaybackReply { succeeded: succeeded }) => {
                                if !succeeded {
                                    error!("error on DMA playback request at destination: {}", destination); break;
                                }
                            },
                            // in case we received status from another destination
                            // but we want to get DmaPlaybackReply anyway, thus the loop
                            Ok(drtioaux::Packet::DmaPlaybackStatus { id: reply_id, destination: dest, error, channel, timestamp }) => {
                                trace.update_state(RemoteState::PlaybackEnded { error: error, channel: channel, timestamp: timestamp });
                            },
                            Ok(_) => { error!("received unsolicited packet while DMA playback"); break; },
                            Err(e) => { error!("error during DMA playback: {}", e); break; }
                        }
                    }
                }
            }
        }
    }
}

#[cfg(not(has_drtio))]
pub mod drtio {
    use super::*;

    pub fn startup(_io: &Io, _aux_mutex: &Mutex,
        _routing_table: &Urc<RefCell<drtio_routing::RoutingTable>>,
        _remote_mgr: &Urc<RefCell<RemoteManager>>,
        _up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>) {}
    pub fn reset(_io: &Io, _aux_mutex: &Mutex) {}
    pub fn dma_send_traces(_io: &Io, _aux_mutex: &Mutex, 
        _routing_table: &drtio_routing::RoutingTable, 
        _remote_mgr: &Urc<RefCell<RemoteManager>>, _id: u32) {}
    pub fn dma_erase(_io: &Io, _aux_mutex: &Mutex, 
        _routing_table: &drtio_routing::RoutingTable, 
        _remote_mgr: &Urc<RefCell<RemoteManager>>,
        _id: u32) {}
    pub fn dma_playback(_io: &Io, _aux_mutex: &Mutex, 
        _routing_table: &drtio_routing::RoutingTable, 
        _remote_mgr: &Urc<RefCell<RemoteManager>>,
        _id: u32, _timestamp: u64) {}

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

fn read_device_map() -> BTreeMap<u32, String> {
    let mut device_map: BTreeMap<u32, String> = BTreeMap::new();
    config::read("device_map", |value: Result<&[u8], config::Error>| {
        let mut bytes = match value {
            Ok(val) => if val.len() > 0 { Cursor::new(val) } else {
                error!("read_device_map: `device_map` was not found in the config");
                return;
            },
            Err(err) => {
                error!("read_device_map: error reading `device_map` from config: {}", err);
                return;
            }
        };
        let size = bytes.read_u32().unwrap();
        for _ in 0..size {
            let channel = bytes.read_u32().unwrap();
            let device_name= bytes.read_string().unwrap();
            if let Some(old_entry) = device_map.insert(channel, device_name.clone()) {
                error!("conflicting entries for channel {}: `{}` and `{}`",
                       channel, old_entry, device_name);
            }
        }
    });
    device_map
}

fn _resolve_channel_name(channel: u32, device_map: &BTreeMap<u32, String>) -> String {
    match device_map.get(&channel) {
        Some(val) => val.clone(),
        None => String::from("unknown")
    }
}

pub fn resolve_channel_name(channel: u32) -> String {
    _resolve_channel_name(channel, unsafe{&RTIO_DEVICE_MAP})
}

pub fn startup(io: &Io, aux_mutex: &Mutex,
        routing_table: &Urc<RefCell<drtio_routing::RoutingTable>>,
        remote_mgr: &Urc<RefCell<RemoteManager>>,
        up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>) {
    unsafe { RTIO_DEVICE_MAP = read_device_map(); }
    drtio::startup(io, aux_mutex, routing_table, up_destinations, remote_mgr);
    unsafe {
        csr::rtio_core::reset_phy_write(1);
    }
    io.spawn(4096, async_error_thread);
}

pub fn reset(io: &Io, aux_mutex: &Mutex) {
    unsafe {
        csr::rtio_core::reset_write(1);
    }
    drtio::reset(io, aux_mutex)
}


pub fn dma_send_traces(io: &Io, aux_mutex: &Mutex, 
    routing_table: &drtio_routing::RoutingTable, 
    remote_mgr: &Urc<RefCell<RemoteManager>>, id: u32) {
    drtio::dma_send_traces(io, aux_mutex, routing_table, remote_mgr, id);
}

pub fn dma_erase(io: &Io, aux_mutex: &Mutex, 
    routing_table: &drtio_routing::RoutingTable, 
    remote_mgr: &Urc<RefCell<RemoteManager>>,
    id: u32) {
    drtio::dma_erase(io, aux_mutex, routing_table, remote_mgr, id);
}

pub fn dma_playback(io: &Io, aux_mutex: &Mutex, 
    routing_table: &drtio_routing::RoutingTable, 
    remote_mgr: &Urc<RefCell<RemoteManager>>,
    id: u32, timestamp: u64) {
    drtio::dma_playback(io, aux_mutex, routing_table, remote_mgr, id, timestamp);
}
