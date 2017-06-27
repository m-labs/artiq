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
        io.spawn(4096, local_error_thread);
        io.spawn(4096, aux_error_thread);
    }

    static mut LINK_RUNNING: bool = false;

    fn link_set_running(running: bool) {
        unsafe {
            LINK_RUNNING = running
        }
    }

    pub fn link_is_running() -> bool {
        unsafe {
            LINK_RUNNING
        }
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
        if link_is_running() {
            unsafe {
                csr::drtio::reset_write(1);
                while csr::drtio::o_wait_read() == 1 {}
            }
            for channel in 0..16 {
                init_channel(channel);
            }
        }
    }

    fn ping_remote(io: &Io) -> u32 {
        let mut count = 0;
        loop {
            if !link_is_up() {
                return 0
            }
            count += 1;
            drtioaux::hw::send(&drtioaux::Packet::EchoRequest).unwrap();
            io.sleep(100).unwrap();
            let pr = drtioaux::hw::recv();
            match pr {
                Ok(Some(drtioaux::Packet::EchoReply)) => return count,
                _ => {}
            }
        }
    }

    pub fn link_thread(io: Io) {
        loop {
            io.until(link_is_up).unwrap();
            info!("link RX is up, pinging");

            let ping_count = ping_remote(&io);
            if ping_count > 0 {
                info!("remote replied after {} packets", ping_count);
                link_set_running(true);
                init();  // clear all FIFOs first
                reset_phy();
                sync_tsc();
                info!("link initialization completed");
            }

            io.until(|| !link_is_up()).unwrap();
            link_set_running(false);
            info!("link is down");
        }
    }

    pub fn local_error_thread(io: Io) {
        loop {
            unsafe {
                io.until(|| csr::drtio::protocol_error_read() != 0).unwrap();
                let errors = csr::drtio::protocol_error_read();
                if errors & 1 != 0 {
                    error!("received packet of an unknown type");
                }
                if errors & 2 != 0 {
                    error!("received truncated packet");
                }
                if errors & 4 != 0 {
                    error!("timeout attempting to get remote FIFO space");
                }
                csr::drtio::protocol_error_write(errors);
            }
        }
    }

    pub fn aux_error_thread(io: Io) {
        loop {
            io.sleep(200).unwrap();
            if link_is_running() {
                drtioaux::hw::send(&drtioaux::Packet::RtioErrorRequest).unwrap();
                match drtioaux::hw::recv_timeout(None) {
                    Ok(drtioaux::Packet::RtioNoErrorReply) => (),
                    Ok(drtioaux::Packet::RtioErrorCollisionReply) => error!("RTIO collision (in satellite)"),
                    Ok(drtioaux::Packet::RtioErrorBusyReply) => error!("RTIO busy (in satellite)"),
                    Ok(_) => error!("received unexpected aux packet"),
                    Err(e) => error!("aux packet error ({})", e)
                }
            }
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
