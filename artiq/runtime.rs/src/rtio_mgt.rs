use config;
use board::csr;
use sched::Scheduler;

#[cfg(has_rtio_crg)]
pub mod crg {
    use clock;
    use board::csr;

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
    use board::csr;
    use sched::{Scheduler, Waiter, Spawner};

    pub fn startup(scheduler: &Scheduler) {
        scheduler.spawner().spawn(4096, link_thread);
        scheduler.spawner().spawn(4096, error_thread);
    }

    fn link_is_up() -> bool {
        unsafe {
            csr::drtio::link_status_read() == 1
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

    pub fn link_thread(waiter: Waiter, _spawner: Spawner) {
        loop {
            waiter.until(link_is_up).unwrap();
            info!("link RX is up");

            waiter.sleep(600).unwrap();
            info!("wait for remote side done");

            sync_tsc();
            info!("TSC synced");
            init();
            info!("link initialization completed");

            waiter.until(|| !link_is_up()).unwrap();
            info!("link is down");
        }
    }

    fn packet_error_present() -> bool {
        unsafe {
            csr::drtio::packet_err_present_read() != 0
        }
    }

    fn get_packet_error() -> u8 {
        unsafe {
            let err = csr::drtio::packet_err_code_read();
            csr::drtio::packet_err_present_write(1);
            err
        }
    }

    pub fn error_thread(waiter: Waiter, _spawner: Spawner) {
        loop {
            waiter.until(packet_error_present).unwrap();
            error!("DRTIO packet error {}", get_packet_error());
        }
    }

}

#[cfg(not(has_drtio))]
mod drtio {
    use sched::Scheduler;

    pub fn startup(_scheduler: &Scheduler) {}
    pub fn init() {}
}

pub fn startup(scheduler: &Scheduler) {
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

    drtio::startup(scheduler);
    init_core()
}

pub fn init_core() {
    unsafe {
        csr::rtio_core::reset_write(1);
    }
    drtio::init()
}
