use core::cell::RefCell;
use urc::Urc;
use board_misoc::csr;
#[cfg(has_drtio))]
use board_misoc::clock;
#[cfg(has_rtio_clock_switch)]
use board_misoc::config;
use board_artiq::drtio_routing;
use sched::Io;

#[cfg(has_rtio_crg)]
pub mod crg {
    use board_misoc::{clock, csr};

    pub fn check() -> bool {
        unsafe { csr::rtio_crg::pll_locked_read() != 0 }
    }

    #[cfg(has_rtio_clock_switch)]
    pub fn init(clk: u8) -> bool {
        unsafe {
            csr::rtio_crg::pll_reset_write(1);
            csr::rtio_crg::clock_sel_write(clk);
            csr::rtio_crg::pll_reset_write(0);
        }
        clock::spin_us(150);
        return check()
    }

    #[cfg(not(has_rtio_clock_switch))]
    pub fn init() -> bool {
        unsafe {
            csr::rtio_crg::pll_reset_write(0);
        }
        clock::spin_us(150);
        return check()
    }
}

#[cfg(not(has_rtio_crg))]
pub mod crg {
    pub fn check() -> bool { true }
}

#[cfg(has_drtio)]
pub mod drtio {
    use super::*;
    use drtioaux;

    pub fn startup(io: &Io, routing_table: &Urc<RefCell<drtio_routing::RoutingTable>>) {
        unsafe {
            csr::drtio_transceiver::stable_clkin_write(1);
        }
        let routing_table = routing_table.clone();
        io.spawn(4096, move |io| {
            let routing_table = routing_table.borrow();
            link_thread(io, &routing_table)
        });
    }

    fn link_rx_up(linkno: u8) -> bool {
        let linkno = linkno as usize;
        unsafe {
            (csr::DRTIO[linkno].rx_up_read)() == 1
        }
    }

    pub fn link_up(linkno: u8) -> bool {
        let linkno = linkno as usize;
        /* This function may be called by kernels with arbitrary
         * linkno values.
         */
        if linkno >= csr::DRTIO.len() {
            return false;
        }
        unsafe {
            (csr::DRTIO[linkno].link_up_read)() == 1
        }
    }

    fn set_link_up(linkno: u8, up: bool) {
        let linkno = linkno as usize;
        unsafe {
            (csr::DRTIO[linkno].link_up_write)(if up { 1 }  else { 0 });
        }
    }

    fn ping_remote(linkno: u8, io: &Io) -> u32 {
        let mut count = 0;
        loop {
            if !link_rx_up(linkno) {
                return 0
            }
            count += 1;
            if count > 200 {
                return 0;
            }
            drtioaux::send(linkno, &drtioaux::Packet::EchoRequest).unwrap();
            io.sleep(100).unwrap();
            let pr = drtioaux::recv(linkno);
            match pr {
                Ok(Some(drtioaux::Packet::EchoReply)) => return count,
                _ => {}
            }
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

    fn sync_tsc(io: &Io, linkno: u8) -> Result<(), &'static str> {
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

    fn load_routing_table(io: &Io, linkno: u8, routing_table: &drtio_routing::RoutingTable)
            -> Result<(), &'static str> {
        for i in 0..drtio_routing::DEST_COUNT {
            drtioaux::send(linkno, &drtioaux::Packet::RoutingSetPath {
                destination: i as u8,
                hops: routing_table.0[i]
            }).unwrap();
            let reply = recv_aux_timeout(io, linkno, 200)?;
            if reply != drtioaux::Packet::RoutingAck {
                return Err("unexpected reply");
            }
        }
        Ok(())
    }

    fn set_rank(io: &Io, linkno: u8, rank: u8) -> Result<(), &'static str> {
        drtioaux::send(linkno, &drtioaux::Packet::RoutingSetRank {
            rank: rank
        }).unwrap();
        let reply = recv_aux_timeout(io, linkno, 200)?;
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

    fn process_unsolicited_aux(linkno: u8) {
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

    fn destination_survey(io: &Io, routing_table: &drtio_routing::RoutingTable,
            up_destinations: &mut [bool; drtio_routing::DEST_COUNT]) {
        for destination in 0..drtio_routing::DEST_COUNT {
            let hop = routing_table.0[destination][0];

            if hop == 0 {
                /* local RTIO */
                if !up_destinations[destination] {
                    info!("[DEST#{}] destination is up", destination);
                    up_destinations[destination] = true;
                }
            } else if hop as usize <= csr::DRTIO.len() {
                let linkno = hop - 1;
                if up_destinations[destination] {
                    if link_up(linkno) {
                        drtioaux::send(linkno, &drtioaux::Packet::DestinationStatusRequest {
                            destination: destination as u8
                        }).unwrap();
                        match recv_aux_timeout(io, linkno, 200) {
                            Ok(drtioaux::Packet::DestinationDownReply) => {
                                info!("[DEST#{}] destination is down", destination);
                                up_destinations[destination] = false;
                            },
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
                        info!("[DEST#{}] destination is down", destination);
                        up_destinations[destination] = false;
                    }
                } else {
                    if link_up(linkno) {
                        drtioaux::send(linkno, &drtioaux::Packet::DestinationStatusRequest {
                            destination: destination as u8
                        }).unwrap();
                        match recv_aux_timeout(io, linkno, 200) {
                            Ok(drtioaux::Packet::DestinationDownReply) => (),
                            Ok(drtioaux::Packet::DestinationOkReply) => {
                                info!("[DEST#{}] destination is up", destination);
                                up_destinations[destination] = true;
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

    pub fn link_thread(io: Io, routing_table: &drtio_routing::RoutingTable) {
        let mut up_destinations = [false; drtio_routing::DEST_COUNT];
        loop {
            for linkno in 0..csr::DRTIO.len() {
                let linkno = linkno as u8;
                if link_up(linkno) {
                    /* link was previously up */
                    if link_rx_up(linkno) {
                        process_unsolicited_aux(linkno);
                        process_local_errors(linkno);
                    } else {
                        info!("[LINK#{}] link is down", linkno);
                        set_link_up(linkno, false);
                    }
                } else {
                    /* link was previously down */
                    if link_rx_up(linkno) {
                        info!("[LINK#{}] link RX became up, pinging", linkno);
                        let ping_count = ping_remote(linkno, &io);
                        if ping_count > 0 {
                            info!("[LINK#{}] remote replied after {} packets", linkno, ping_count);
                            set_link_up(linkno, true);
                            if let Err(e) = sync_tsc(&io, linkno) {
                                error!("[LINK#{}] failed to sync TSC ({})", linkno, e);
                            }
                            if let Err(e) = load_routing_table(&io, linkno, routing_table) {
                                error!("[LINK#{}] failed to load routing table ({})", linkno, e);
                            }
                            if let Err(e) = set_rank(&io, linkno, 1) {
                                error!("[LINK#{}] failed to set rank ({})", linkno, e);
                            }
                            info!("[LINK#{}] link initialization completed", linkno);
                        } else {
                            error!("[LINK#{}] ping failed", linkno);
                        }
                    }
                }
            }
            destination_survey(&io, routing_table, &mut up_destinations);
            io.sleep(200).unwrap();
        }
    }

    pub fn init() {
        for linkno in 0..csr::DRTIO.len() {
            let linkno = linkno as u8;
            if link_up(linkno) {
                drtioaux::send(linkno,
                    &drtioaux::Packet::ResetRequest { phy: false }).unwrap();
                match drtioaux::recv_timeout(linkno, None) {
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

    pub fn startup(_io: &Io, _routing_table: &Urc<RefCell<drtio_routing::RoutingTable>>) {}
    pub fn init() {}
    pub fn link_up(_linkno: u8) -> bool { false }
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

pub fn startup(io: &Io, routing_table: &Urc<RefCell<drtio_routing::RoutingTable>>) {
    #[cfg(has_rtio_crg)]
    {
        #[cfg(has_rtio_clock_switch)]
        {
            #[derive(Debug)]
            enum RtioClock {
                Internal = 0,
                External = 1
            };

            let clk = config::read("rtio_clock", |result| {
                match result {
                    Ok(b"i") => {
                        info!("using internal RTIO clock");
                        RtioClock::Internal
                    },
                    Ok(b"e") => {
                        info!("using external RTIO clock");
                        RtioClock::External
                    },
                    _ => {
                        info!("using internal RTIO clock (by default)");
                        RtioClock::Internal
                    },
                }
            });

            if !crg::init(clk as u8) {
                error!("RTIO clock failed");
            }
        }
        #[cfg(not(has_rtio_clock_switch))]
        {
            if !crg::init() {
                error!("RTIO clock failed");
            }
        }
    }

    #[cfg(has_drtio_routing)]
    {
        let routing_table = routing_table.clone();
        drtio_routing::program_interconnect(&routing_table.borrow(), 0);
    }

    drtio::startup(io, &routing_table);
    init_core(true);
    io.spawn(4096, async_error_thread);
}

pub fn init_core(phy: bool) {
    unsafe {
        csr::rtio_core::reset_write(1);
        if phy {
            csr::rtio_core::reset_phy_write(1);
        }
    }
    drtio::init()
}
