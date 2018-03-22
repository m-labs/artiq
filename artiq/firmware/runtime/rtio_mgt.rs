use board::{csr, config};
use sched::Io;

#[cfg(has_rtio_crg)]
pub mod crg {
    use board::{clock, csr};

    pub fn init() {
        unsafe { csr::rtio_crg::pll_reset_write(0) }
    }

    pub fn check() -> bool {
        unsafe { csr::rtio_crg::pll_locked_read() != 0 }
    }

    pub fn switch_clock(clk: u8) -> bool {
        unsafe {
            let cur_clk = csr::rtio_crg::clock_sel_read();
            if clk != cur_clk {
                csr::rtio_crg::pll_reset_write(1);
                csr::rtio_crg::clock_sel_write(clk);
                csr::rtio_crg::pll_reset_write(0);
            }
        }

        clock::spin_us(150);
        return check()
    }
}

#[cfg(not(has_rtio_crg))]
pub mod crg {
    pub fn init() {}
    pub fn check() -> bool { true }
    pub fn switch_clock(_clk: u8) -> bool { true }
}

#[cfg(has_drtio)]
pub mod drtio {
    use super::*;
    use drtioaux;

    pub fn startup(io: &Io) {
        unsafe {
            csr::drtio_transceiver::stable_clkin_write(1);
        }
        io.spawn(4096, link_thread);
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

    fn sync_tsc(linkno: u8) {
        let linkno = linkno as usize;
        unsafe {
            (csr::DRTIO[linkno].set_time_write)(1);
            while (csr::DRTIO[linkno].set_time_read)() == 1 {}
        }
    }

    fn init_buffer_space(linkno: u8) {
        let linkidx = linkno as usize;
        unsafe {
            (csr::DRTIO[linkidx].o_get_buffer_space_write)(1);
            while (csr::DRTIO[linkidx].o_wait_read)() == 1 {}
            info!("[LINK#{}] buffer space is {}",
                linkno, (csr::DRTIO[linkidx].o_dbg_buffer_space_read)());
        }
    }

    fn ping_remote(linkno: u8, io: &Io) -> u32 {
        let mut count = 0;
        loop {
            if !link_rx_up(linkno) {
                return 0
            }
            count += 1;
            drtioaux::hw::send_link(linkno, &drtioaux::Packet::EchoRequest).unwrap();
            io.sleep(100).unwrap();
            let pr = drtioaux::hw::recv_link(linkno);
            match pr {
                Ok(Some(drtioaux::Packet::EchoReply)) => return count,
                _ => {}
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

    fn process_aux_errors(linkno: u8) {
        drtioaux::hw::send_link(linkno, &drtioaux::Packet::RtioErrorRequest).unwrap();
        match drtioaux::hw::recv_timeout_link(linkno, None) {
            Ok(drtioaux::Packet::RtioNoErrorReply) => (),
            Ok(drtioaux::Packet::RtioErrorSequenceErrorReply { channel }) =>
                error!("[LINK#{}] RTIO sequence error involving channel {}", linkno, channel),
            Ok(drtioaux::Packet::RtioErrorCollisionReply { channel }) =>
                error!("[LINK#{}] RTIO collision involving channel {}", linkno, channel),
            Ok(drtioaux::Packet::RtioErrorBusyReply { channel }) =>
                error!("[LINK#{}] RTIO busy error involving channel {}", linkno, channel),
            Ok(_) => error!("[LINK#{}] received unexpected aux packet", linkno),
            Err(e) => error!("[LINK#{}] aux packet error ({})", linkno, e)
        }
    }
    
    pub fn link_thread(io: Io) {
        loop {
            for linkno in 0..csr::DRTIO.len() {
                let linkno = linkno as u8;
                if link_up(linkno) {
                    /* link was previously up */
                    if link_rx_up(linkno) {
                        process_local_errors(linkno);
                        process_aux_errors(linkno);
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
                            init_buffer_space(linkno);
                            sync_tsc(linkno);
                            info!("[LINK#{}] link initialization completed", linkno);
                        } else {
                            info!("[LINK#{}] ping failed", linkno);
                        }
                    }
                }
            }
            io.sleep(200).unwrap();
        }
    }

    pub fn init() {
        for linkno in 0..csr::DRTIO.len() {
            let linkno = linkno as u8;
            if link_up(linkno) {
                drtioaux::hw::send_link(linkno,
                    &drtioaux::Packet::ResetRequest { phy: false }).unwrap();
                match drtioaux::hw::recv_timeout_link(linkno, None) {
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

    pub fn startup(_io: &Io) {}
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

pub fn startup(io: &Io) {
    crg::init();

    #[derive(Debug)]
    enum RtioClock {
        Internal = 0,
        External = 1
    };

    let clk = config::read("startup_clock", |result| {
        match result {
            Ok(b"i") => {
                info!("using internal startup RTIO clock");
                RtioClock::Internal
            },
            Ok(b"e") => {
                info!("using external startup RTIO clock");
                RtioClock::External
            },
            Err(_) => {
                info!("using internal startup RTIO clock (by default)");
                RtioClock::Internal
            },
            Ok(_) => {
                error!("unrecognized startup_clock configuration entry, \
                        using internal RTIO clock");
                RtioClock::Internal
            }
        }
    });

    if !crg::switch_clock(clk as u8) {
        error!("startup RTIO clock failed");
        warn!("this may cause the system initialization to fail");
        warn!("fix clocking and reset the device");
    }

    drtio::startup(io);
    init_core();
    io.spawn(4096, async_error_thread);
}

pub fn init_core() {
    unsafe {
        csr::rtio_core::reset_write(1);
        csr::rtio_core::reset_phy_write(1);
    }
    drtio::init()
}

#[cfg(has_drtio)]
pub mod drtio_dbg {
    use board::csr;

    pub fn get_packet_counts(linkno: u8) -> (u32, u32) {
        let linkno = linkno as usize;
        unsafe {
            (csr::DRTIO[linkno].update_packet_cnt_write)(1);
            ((csr::DRTIO[linkno].packet_cnt_tx_read)(),
             (csr::DRTIO[linkno].packet_cnt_rx_read)())
        }
    }

    pub fn get_buffer_space_req_count(linkno: u8) -> u32 {
        let linkno = linkno as usize;
        unsafe {
            (csr::DRTIO[linkno].o_dbg_buffer_space_req_cnt_read)()
        }
    }
}

#[cfg(not(has_drtio))]
pub mod drtio_dbg {
    pub fn get_packet_counts(_linkno: u8) -> (u32, u32) { (0, 0) }

    pub fn get_buffer_space_req_count(_linkno: u8) -> u32 { 0 }
}
