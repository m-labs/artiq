use config;

#[cfg(has_rtio_crg)]
mod imp {
    use board::csr;
    use clock;

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
mod imp {
    pub fn init() {}
    pub fn check() -> bool { true }
    pub fn switch_clock(clk: u8) -> bool { true }
}

pub fn init() {
    imp::init();

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

    if !switch_clock(clk) {
        error!("startup RTIO clock failed");
        warn!("this may cause the system initialization to fail");
        warn!("fix clocking and reset the device");
    }
}

pub use self::imp::{check, switch_clock};
