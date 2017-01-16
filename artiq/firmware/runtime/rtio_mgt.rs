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
mod drtio {
    use super::*;

    pub fn startup(io: &Io) {
        io.spawn(4096, link_thread);
        io.spawn(4096, error_thread);
    }

    fn link_is_up() -> bool {
        unsafe {
            csr::drtio::link_status_read() == 1
        }
    }

    fn reset_phy() {
        unsafe {
            csr::drtio::reset_phy_write(1);
            while csr::drtio::o_wait_read() == 1 {}
        }
    }

    fn sync_tsc() {
        unsafe {
            csr::drtio::set_time_write(1);
            while csr::drtio::set_time_read() == 1 {}
        }
    }

    fn init_channel(channel: u16) {
        unsafe {
            csr::drtio::chan_sel_override_write(channel);
            csr::drtio::chan_sel_override_en_write(1);

            csr::drtio::o_reset_channel_status_write(1);
            csr::drtio::o_get_fifo_space_write(1);
            while csr::drtio::o_wait_read() == 1 {}
            info!("FIFO space on channel {} is {}", channel, csr::drtio::o_dbg_fifo_space_read());

            csr::drtio::chan_sel_override_en_write(0);
        }
    }

    pub fn init() {
        if link_is_up() {
            unsafe {
                csr::drtio::reset_write(1);
                while csr::drtio::o_wait_read() == 1 {}
            }
            for channel in 0..16 {
                init_channel(channel);
            }
        }
    }

    pub fn link_thread(io: Io) {
        loop {
            io.until(link_is_up).unwrap();
            info!("link RX is up");

            io.sleep(600).unwrap();
            info!("wait for remote side done");

            init();  // clear all FIFOs first
            reset_phy();
            sync_tsc();
            info!("link initialization completed");

            io.until(|| !link_is_up()).unwrap();
            info!("link is down");
        }
    }

    // keep this in sync with error_codes in rt_packets.py
    fn str_packet_error(err_code: u8) -> &'static str {
        match err_code {
            0 => "Received packet of an unknown type",
            1 => "Satellite reported reception of a packet of an unknown type",
            2 => "Received truncated packet",
            3 => "Satellite reported reception of a truncated packet",
            4 => "Satellite reported write overflow",
            5 => "Satellite reported write underflow",
            _ => "Unknown error code"
        }
    }

    fn poll_errors() -> bool {
        unsafe {
            if csr::drtio::packet_err_present_read() != 0 {
                let err_code = csr::drtio::packet_err_code_read();
                error!("packet error {} ({})", err_code, str_packet_error(err_code));
                csr::drtio::packet_err_present_write(1)
            }
            if csr::drtio::o_fifo_space_timeout_read() != 0 {
                error!("timeout attempting to get remote FIFO space");
                csr::drtio::o_fifo_space_timeout_write(1)
            }
        }
        false
    }

    pub fn error_thread(io: Io) {
        // HACK
        io.until(poll_errors).unwrap();
    }
}

#[cfg(not(has_drtio))]
mod drtio {
    use super::*;

    pub fn startup(_io: &Io) {}
    pub fn init() {}
}

pub fn startup(io: &Io) {
    crg::init();

    let mut opt = [b'i'];
    let clk;
    match config::read("startup_clock", &mut opt) {
        Ok(0) | Ok(1) if &opt == b"i" => {
            info!("startup RTIO clock: internal");
            clk = 0
        }
        Ok(1) if &opt == b"e" => {
            info!("startup RTIO clock: external");
            clk = 1
        }
        _ => {
            error!("unrecognized startup_clock configuration entry");
            clk = 0
        }
    };

    if !crg::switch_clock(clk) {
        error!("startup RTIO clock failed");
        warn!("this may cause the system initialization to fail");
        warn!("fix clocking and reset the device");
    }

    drtio::startup(io);
    init_core()
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

    pub fn get_channel_state(channel: u32) -> (u16, u64) {
        unsafe {
            csr::drtio::chan_sel_override_write(channel as u16);
            csr::drtio::chan_sel_override_en_write(1);
            let fifo_space = csr::drtio::o_dbg_fifo_space_read();
            let last_timestamp = csr::drtio::o_dbg_last_timestamp_read();
            csr::drtio::chan_sel_override_en_write(0);
            (fifo_space, last_timestamp)
        }
    }

    pub fn reset_channel_state(channel: u32) {
        unsafe {
            csr::drtio::chan_sel_override_write(channel as u16);
            csr::drtio::chan_sel_override_en_write(1);
            csr::drtio::o_reset_channel_status_write(1);
            csr::drtio::chan_sel_override_en_write(0);
        }
    }

    pub fn get_fifo_space(channel: u32) {
        unsafe {
            csr::drtio::chan_sel_override_write(channel as u16);
            csr::drtio::chan_sel_override_en_write(1);
            csr::drtio::o_get_fifo_space_write(1);
            csr::drtio::chan_sel_override_en_write(0);
        }
    }

    pub fn get_packet_counts() -> (u32, u32) {
        unsafe {
            csr::drtio::update_packet_cnt_write(1);
            (csr::drtio::packet_cnt_tx_read(), csr::drtio::packet_cnt_rx_read())
        }
    }

    pub fn get_fifo_space_req_count() -> u32 {
        unsafe {
            csr::drtio::o_dbg_fifo_space_req_cnt_read()
        }
    }
}

#[cfg(not(has_drtio))]
pub mod drtio_dbg {
    pub fn get_channel_state(_channel: u32) -> (u16, u64) { (0, 0) }

    pub fn reset_channel_state(_channel: u32) {}

    pub fn get_fifo_space(_channel: u32) {}

    pub fn get_packet_counts() -> (u32, u32) { (0, 0) }

    pub fn get_fifo_space_req_count() -> u32 { 0 }
}
