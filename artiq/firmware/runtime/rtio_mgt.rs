use core::cell::RefCell;
use urc::Urc;
use board_misoc::csr;
#[cfg(has_drtio)]
use board_misoc::clock;
use board_artiq::drtio_routing;
use sched::Io;
use sched::Mutex;

#[cfg(has_drtio)]
pub mod drtio {
    use super::*;
    use drtioaux;

    pub fn startup(io: &Io, aux_mutex: &Mutex,
            routing_table: &Urc<RefCell<drtio_routing::RoutingTable>>,
            up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>) {
        let aux_mutex = aux_mutex.clone();
        let routing_table = routing_table.clone();
        let up_destinations = up_destinations.clone();
        io.spawn(4096, move |io| {
            let routing_table = routing_table.borrow();
            link_thread(io, &aux_mutex, &routing_table, &up_destinations);
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
                Ok(drtioaux::Packet::EchoReply) => return count,
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

    fn process_unsolicited_aux(io: &Io, aux_mutex: &Mutex, linkno: u8) {
        let _lock = aux_mutex.lock(io).unwrap();
        match drtioaux::recv(linkno) {
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
            up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>) {
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
                            Ok(drtioaux::Packet::DestinationDownReply) =>
                                destination_set_up(routing_table, up_destinations, destination, false),
                            Ok(drtioaux::Packet::DestinationOkReply) => (),
                            Ok(drtioaux::Packet::DestinationSequenceErrorReply { channel }) =>
                                error!("[DEST#{}] RTIO sequence error involving channel 0x{:04x}", destination, channel),
                            Ok(drtioaux::Packet::DestinationCollisionReply { channel }) =>
                                error!("[DEST#{}] RTIO collision involving channel 0x{:04x}", destination, channel),
                            Ok(drtioaux::Packet::DestinationBusyReply { channel }) =>
                                error!("[DEST#{}] RTIO busy error involving channel 0x{:04x}", destination, channel),
                            Ok(packet) => error!("[DEST#{}] received unexpected aux packet: {:?}", destination, packet),
                            Err(e) => error!("[DEST#{}] communication failed ({})", destination, e)
                        }
                    } else {
                        destination_set_up(routing_table, up_destinations, destination, false);
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
            up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>) {
        let mut up_links = [false; csr::DRTIO.len()];
        loop {
            for linkno in 0..csr::DRTIO.len() {
                let linkno = linkno as u8;
                if up_links[linkno as usize] {
                    /* link was previously up */
                    if link_rx_up(linkno) {
                        process_unsolicited_aux(&io, aux_mutex, linkno);
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
            destination_survey(&io, aux_mutex, routing_table, &up_links, up_destinations);
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
}

#[cfg(not(has_drtio))]
pub mod drtio {
    use super::*;

    pub fn startup(_io: &Io, _aux_mutex: &Mutex,
        _routing_table: &Urc<RefCell<drtio_routing::RoutingTable>>,
        _up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>) {}
    pub fn reset(_io: &Io, _aux_mutex: &Mutex) {}
}

fn async_error_thread(io: Io) {
    loop {
        unsafe {
            io.until(|| csr::rtio_core::async_error_read() != 0).unwrap();
            let errors = csr::rtio_core::async_error_read();
            if errors & 1 != 0 {
                error!("RTIO collision involving channel {}",
                       csr::rtio_core::collision_channel_read());
            }
            if errors & 2 != 0 {
                error!("RTIO busy error involving channel {}",
                       csr::rtio_core::busy_channel_read());
            }
            if errors & 4 != 0 {
                error!("RTIO sequence error involving channel {}",
                       csr::rtio_core::sequence_error_channel_read());
            }
            csr::rtio_core::async_error_write(errors);
        }
    }
}

pub fn startup(io: &Io, aux_mutex: &Mutex,
        routing_table: &Urc<RefCell<drtio_routing::RoutingTable>>,
        up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>) {
    drtio::startup(io, aux_mutex, routing_table, up_destinations);
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
