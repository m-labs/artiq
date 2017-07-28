use config;
use board::csr;
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
        io.spawn(4096, link_thread);
    }

    fn link_rx_up(linkno: u8) -> bool {
        let linkno = linkno as usize;
        unsafe {
            (csr::DRTIO[linkno].link_status_read)() == 1
        }
    }

    fn reset_phy(linkno: u8) {
        let linkno = linkno as usize;
        unsafe {
            (csr::DRTIO[linkno].reset_phy_write)(1);
            while (csr::DRTIO[linkno].o_wait_read)() == 1 {}
        }
    }

    fn sync_tsc(linkno: u8) {
        let linkno = linkno as usize;
        unsafe {
            (csr::DRTIO[linkno].set_time_write)(1);
            while (csr::DRTIO[linkno].set_time_read)() == 1 {}
        }
    }

    fn init_link(linkno: u8) {
        let linkidx = linkno as usize;
        unsafe {
            (csr::DRTIO[linkidx].reset_write)(1);
            while (csr::DRTIO[linkidx].o_wait_read)() == 1 {}
        }
        // TODO: determine actual number of remote FIFOs
        for channel in 0..16 {
            unsafe {
                (csr::DRTIO[linkidx].chan_sel_override_write)(channel);
                (csr::DRTIO[linkidx].chan_sel_override_en_write)(1);

                (csr::DRTIO[linkidx].o_reset_channel_status_write)(1);
                (csr::DRTIO[linkidx].o_get_fifo_space_write)(1);
                while (csr::DRTIO[linkidx].o_wait_read)() == 1 {}
                info!("[LINK#{}] FIFO space on channel {} is {}",
                    linkno, channel, (csr::DRTIO[linkidx].o_dbg_fifo_space_read)());

                (csr::DRTIO[linkidx].chan_sel_override_en_write)(0);
            }
        }
    }

    pub fn init() {
        for linkno in 0..csr::DRTIO.len() {
            init_link(linkno as u8);
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
            error!("[LINK#{}] found error(s)", linkno);
            if errors & 1 != 0 {
                error!("[LINK#{}] received packet of an unknown type", linkno);
            }
            if errors & 2 != 0 {
                error!("[LINK#{}] received truncated packet", linkno);
            }
            if errors & 4 != 0 {
                error!("[LINK#{}] timeout attempting to get remote FIFO space", linkno);
            }
        }
    }

    fn process_aux_errors(linkno: u8) {
        drtioaux::hw::send_link(linkno, &drtioaux::Packet::RtioErrorRequest).unwrap();
        match drtioaux::hw::recv_timeout_link(linkno, None) {
            Ok(drtioaux::Packet::RtioNoErrorReply) => (),
            Ok(drtioaux::Packet::RtioErrorCollisionReply) =>
                error!("[LINK#{}] RTIO collision", linkno),
            Ok(drtioaux::Packet::RtioErrorBusyReply) =>
                error!("[LINK#{}] RTIO busy", linkno),
            Ok(_) => error!("[LINK#{}] received unexpected aux packet", linkno),
            Err(e) => error!("[LINK#{}] aux packet error ({})", linkno, e)
        }
    }

    pub fn link_thread(io: Io) {
        let mut link_up = vec![false; csr::DRTIO.len()];

        loop {
            for linkno in 0..csr::DRTIO.len() {
                let linkno = linkno as u8;
                if !link_up[linkno as usize] {
                    if link_rx_up(linkno) {
                        info!("[LINK#{}] link RX became up, pinging", linkno);
                        let ping_count = ping_remote(linkno, &io);
                        if ping_count > 0 {
                            info!("[LINK#{}] remote replied after {} packets", linkno, ping_count);
                            init_link(linkno);  // clear all FIFOs first
                            reset_phy(linkno);
                            sync_tsc(linkno);
                            info!("[LINK#{}] link initialization completed", linkno);
                            link_up[linkno as usize] = true;
                        } else {
                            info!("[LINK#{}] ping failed", linkno);
                        }
                    } else {
                        if link_rx_up(linkno) {
                            process_local_errors(linkno);
                            process_aux_errors(linkno);
                        } else {
                            info!("[LINK#{}] link is down", linkno);
                            link_up[linkno as usize] = false;
                        }
                    }
                }
            }
            io.sleep(200).unwrap();
        }
    }
}

#[cfg(not(has_drtio))]
mod drtio {
    use super::*;

    pub fn startup(_io: &Io) {}
    pub fn init() {}
}

fn async_error_thread(io: Io) {
    loop {
        unsafe {
            io.until(|| csr::rtio_core::async_error_read() != 0).unwrap();
            let errors = csr::rtio_core::async_error_read();
            if errors & 1 != 0 {
                error!("RTIO collision");
            }
            if errors & 2 != 0 {
                error!("RTIO busy");
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
            Ok(b"i") => RtioClock::Internal,
            Ok(b"e") => RtioClock::External,
            _ => {
                error!("unrecognized startup_clock configuration entry");
                RtioClock::Internal
            }
        }
    });

    info!("startup RTIO clock: {:?}", clk);
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
    }
    drtio::init()
}

#[cfg(has_drtio)]
pub mod drtio_dbg {
    use board::csr;

    // TODO: routing
    pub fn get_channel_state(channel: u32) -> (u16, u64) {
        let linkno = ((channel >> 16) - 1) as usize;
        let node_channel = channel as u16;
        unsafe {
            (csr::DRTIO[linkno].chan_sel_override_write)(node_channel as u16);
            (csr::DRTIO[linkno].chan_sel_override_en_write)(1);
            let fifo_space = (csr::DRTIO[linkno].o_dbg_fifo_space_read)();
            let last_timestamp = (csr::DRTIO[linkno].o_dbg_last_timestamp_read)();
            (csr::DRTIO[linkno].chan_sel_override_en_write)(0);
            (fifo_space, last_timestamp)
        }
    }

    pub fn reset_channel_state(channel: u32) {
        let linkno = ((channel >> 16) - 1) as usize;
        let node_channel = channel as u16;
        unsafe {
            (csr::DRTIO[linkno].chan_sel_override_write)(node_channel);
            (csr::DRTIO[linkno].chan_sel_override_en_write)(1);
            (csr::DRTIO[linkno].o_reset_channel_status_write)(1);
            (csr::DRTIO[linkno].chan_sel_override_en_write)(0);
        }
    }

    pub fn get_fifo_space(channel: u32) {
        let linkno = ((channel >> 16) - 1) as usize;
        let node_channel = channel as u16;
        unsafe {
            (csr::DRTIO[linkno].chan_sel_override_write)(node_channel);
            (csr::DRTIO[linkno].chan_sel_override_en_write)(1);
            (csr::DRTIO[linkno].o_get_fifo_space_write)(1);
            (csr::DRTIO[linkno].chan_sel_override_en_write)(0);
        }
    }

    pub fn get_packet_counts(linkno: u8) -> (u32, u32) {
        let linkno = linkno as usize;
        unsafe {
            (csr::DRTIO[linkno].update_packet_cnt_write)(1);
            ((csr::DRTIO[linkno].packet_cnt_tx_read)(),
             (csr::DRTIO[linkno].packet_cnt_rx_read)())
        }
    }

    pub fn get_fifo_space_req_count(linkno: u8) -> u32 {
        let linkno = linkno as usize;
        unsafe {
            (csr::DRTIO[linkno].o_dbg_fifo_space_req_cnt_read)()
        }
    }
}

#[cfg(not(has_drtio))]
pub mod drtio_dbg {
    pub fn get_channel_state(_channel: u32) -> (u16, u64) { (0, 0) }

    pub fn reset_channel_state(_channel: u32) {}

    pub fn get_fifo_space(_channel: u32) {}

    pub fn get_packet_counts(_linkno: u8) -> (u32, u32) { (0, 0) }

    pub fn get_fifo_space_req_count(_linkno: u8) -> u32 { 0 }
}
