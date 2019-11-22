use board_misoc::config;
#[cfg(si5324_as_synthesizer)]
use board_artiq::si5324;
#[cfg(has_drtio)]
use board_misoc::csr;

#[derive(Debug)]
pub enum RtioClock {
    Internal = 0,
    External = 1
}

fn get_rtio_clock_cfg() -> RtioClock {
    config::read("rtio_clock", |result| {
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
    })
}

#[cfg(has_rtio_crg)]
pub mod crg {
    #[cfg(has_rtio_clock_switch)]
    use super::RtioClock;
    use board_misoc::{clock, csr};

    pub fn check() -> bool {
        unsafe { csr::rtio_crg::pll_locked_read() != 0 }
    }

    #[cfg(has_rtio_clock_switch)]
    pub fn init(clk: RtioClock) -> bool {
        unsafe {
            csr::rtio_crg::pll_reset_write(1);
            csr::rtio_crg::clock_sel_write(clk as u8);
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

#[cfg(si5324_as_synthesizer)]
fn setup_si5324_as_synthesizer() {
    // 125 MHz output from 10 MHz CLKIN2, 504 Hz BW
    #[cfg(all(rtio_frequency = "125.0", si5324_ext_ref, ext_ref_frequency = "10.0"))]
    const SI5324_SETTINGS: si5324::FrequencySettings
        = si5324::FrequencySettings {
        n1_hs  : 10,
        nc1_ls : 4,
        n2_hs  : 10,
        n2_ls  : 300,
        n31    : 75,
        n32    : 6,
        bwsel  : 4,
        crystal_ref: false
    };
    // 125MHz output, from 100MHz CLKIN2 reference, 586 Hz loop bandwidth
    #[cfg(all(rtio_frequency = "125.0", si5324_ext_ref, ext_ref_frequency = "100.0"))]
    const SI5324_SETTINGS: si5324::FrequencySettings
        = si5324::FrequencySettings {
        n1_hs  : 10,
        nc1_ls : 4,
        n2_hs  : 10,
        n2_ls  : 260,
        n31    : 65,
        n32    : 52,
        bwsel  : 4,
        crystal_ref: false
    };
    // 125MHz output, from 125MHz CLKIN2 reference, 606 Hz loop bandwidth
    #[cfg(all(rtio_frequency = "125.0", si5324_ext_ref, ext_ref_frequency = "125.0"))]
    const SI5324_SETTINGS: si5324::FrequencySettings
        = si5324::FrequencySettings {
        n1_hs  : 5,
        nc1_ls : 8,
        n2_hs  : 7,
        n2_ls  : 360,
        n31    : 63,
        n32    : 63,
        bwsel  : 4,
        crystal_ref: false
    };
    // 125MHz output, from crystal, 7 Hz
    #[cfg(all(rtio_frequency = "125.0", not(si5324_ext_ref)))]
    const SI5324_SETTINGS: si5324::FrequencySettings
        = si5324::FrequencySettings {
        n1_hs  : 10,
        nc1_ls : 4,
        n2_hs  : 10,
        n2_ls  : 19972,
        n31    : 4993,
        n32    : 4565,
        bwsel  : 4,
        crystal_ref: true
    };
    // 150MHz output, from crystal
    #[cfg(all(rtio_frequency = "150.0", not(si5324_ext_ref)))]
    const SI5324_SETTINGS: si5324::FrequencySettings
        = si5324::FrequencySettings {
        n1_hs  : 9,
        nc1_ls : 4,
        n2_hs  : 10,
        n2_ls  : 33732,
        n31    : 9370,
        n32    : 7139,
        bwsel  : 3,
        crystal_ref: true
    };
    // 100MHz output, from crystal. Also used as reference for Sayma HMC830.
    #[cfg(all(rtio_frequency = "100.0", not(si5324_ext_ref)))]
    const SI5324_SETTINGS: si5324::FrequencySettings
        = si5324::FrequencySettings {
        n1_hs  : 9,
        nc1_ls : 6,
        n2_hs  : 10,
        n2_ls  : 33732,
        n31    : 9370,
        n32    : 7139,
        bwsel  : 3,
        crystal_ref: true
    };
    si5324::setup(&SI5324_SETTINGS, si5324::Input::Ckin2).expect("cannot initialize Si5324");
}

pub fn init() {
    #[cfg(si5324_as_synthesizer)]
    {
        match get_rtio_clock_cfg() {
            RtioClock::Internal => setup_si5324_as_synthesizer(),
            RtioClock::External => si5324::bypass(si5324::Input::Ckin2).expect("cannot bypass Si5324")
        }
    }

    #[cfg(has_drtio)]
    unsafe {
        csr::drtio_transceiver::stable_clkin_write(1);
    }

    #[cfg(has_rtio_crg)]
    {
        #[cfg(has_rtio_clock_switch)]
        let result = crg::init(get_rtio_clock_cfg());
        #[cfg(not(has_rtio_clock_switch))]
        let result = crg::init();
        if !result {
            error!("RTIO clock failed");
        }
    }
}
