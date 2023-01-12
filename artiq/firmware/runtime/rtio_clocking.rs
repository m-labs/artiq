use board_misoc::config;
#[cfg(si5324_as_synthesizer)]
use board_artiq::si5324;
use board_misoc::{csr, clock};

#[derive(Debug, PartialEq)]
#[allow(non_camel_case_types)]
pub enum RtioClock {
    Default,
    Int_125,
    Int_100,
    Ext0_Bypass,
    Ext0_Synth0_10to125,
    Ext0_Synth0_100to125,
    Ext0_Synth0_125to125,
}

#[allow(unreachable_code)]
fn get_rtio_clock_cfg() -> RtioClock {
    config::read_str("rtio_clock", |result| { 
        let res = match result {
            Ok("int_125") => RtioClock::Int_125,
            Ok("int_100") => RtioClock::Int_100,
            Ok("ext0_bypass") => RtioClock::Ext0_Bypass,
            Ok("ext0_bypass_125") => RtioClock::Ext0_Bypass,
            Ok("ext0_bypass_100") => RtioClock::Ext0_Bypass,
            Ok("ext0_synth0_10to125") => RtioClock::Ext0_Synth0_10to125,
            Ok("ext0_synth0_100to125") => RtioClock::Ext0_Synth0_100to125,
            Ok("ext0_synth0_125to125") => RtioClock::Ext0_Synth0_125to125,
            Ok("i") => {
                warn!("Using legacy rtio_clock setting ('i'). Falling back to default. This will be deprecated.");
                RtioClock::Default
            },
            Ok("e") => {
                warn!("Using legacy rtio_clock setting ('e'). This will be deprecated.");
                RtioClock::Ext0_Bypass
            },
            _ => {
                warn!("rtio_clock setting not recognised. Falling back to default.");
                RtioClock::Default
            }
        };
        if res == RtioClock::Default {
            #[cfg(any(si5324_ext_ref, ext_ref_frequency))]
            warn!("si5324_ext_ref and ext_ref_frequency compile-time options are deprecated. Please use the rtio_clock coreconfig settings instead.");
            #[cfg(all(rtio_frequency = "125.0", si5324_ext_ref, ext_ref_frequency = "10.0"))]
            return RtioClock::Ext0_Synth0_10to125;
            #[cfg(all(rtio_frequency = "125.0", si5324_ext_ref, ext_ref_frequency = "100.0"))]
            return RtioClock::Ext0_Synth0_100to125;
            #[cfg(all(rtio_frequency = "125.0", si5324_ext_ref, ext_ref_frequency = "125.0"))]
            return RtioClock::Ext0_Synth0_125to125;
            #[cfg(all(rtio_frequency = "125.0", not(si5324_ext_ref)))]
            return RtioClock::Int_125;
            #[cfg(all(rtio_frequency = "100.0", not(si5324_ext_ref), not(soc_platform = "kasli")))]
            return RtioClock::Int_100;
            //in case nothing is set
            return RtioClock::Int_125;
        }
        res
     })

}

#[cfg(has_rtio_crg)]
pub mod crg {
    use board_misoc::{clock, csr};

    pub fn check() -> bool {
        unsafe { csr::rtio_crg::pll_locked_read() != 0 }
    }

    pub fn init() -> bool {
        info!("Using internal RTIO clock");
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

// Si5324 input to select for locking to an external clock (as opposed to
// a recovered link clock in DRTIO satellites, which is handled elsewhere).
#[cfg(all(si5324_as_synthesizer, soc_platform = "kasli", hw_rev = "v2.0"))]
const SI5324_EXT_INPUT: si5324::Input = si5324::Input::Ckin1;
#[cfg(all(si5324_as_synthesizer, soc_platform = "kasli", not(hw_rev = "v2.0")))]
const SI5324_EXT_INPUT: si5324::Input = si5324::Input::Ckin2;
#[cfg(all(si5324_as_synthesizer, soc_platform = "kc705"))]
const SI5324_EXT_INPUT: si5324::Input = si5324::Input::Ckin2;

#[cfg(si5324_as_synthesizer)]
fn setup_si5324_as_synthesizer(cfg: RtioClock) {
    let (si5324_settings, si5324_ref_input) = match cfg {
        RtioClock::Ext0_Synth0_10to125 => { // 125 MHz output from 10 MHz CLKINx reference, 504 Hz BW
            info!("using 10MHz reference to make 125MHz RTIO clock with PLL");
            (
                si5324::FrequencySettings {
                    n1_hs  : 10,
                    nc1_ls : 4,
                    n2_hs  : 10,
                    n2_ls  : 300,
                    n31    : 6,
                    n32    : 6,
                    bwsel  : 4,
                    crystal_as_ckin2: false
                },
                SI5324_EXT_INPUT
            )
        },
        RtioClock::Ext0_Synth0_100to125 => { // 125MHz output, from 100MHz CLKINx reference, 586 Hz loop bandwidth
            info!("using 100MHz reference to make 125MHz RTIO clock with PLL");
            (
                si5324::FrequencySettings {
                    n1_hs  : 10,
                    nc1_ls : 4,
                    n2_hs  : 10,
                    n2_ls  : 260,
                    n31    : 52,
                    n32    : 52,
                    bwsel  : 4,
                    crystal_as_ckin2: false
                },
                SI5324_EXT_INPUT
            )
        },
        RtioClock::Ext0_Synth0_125to125 => { // 125MHz output, from 125MHz CLKINx reference, 606 Hz loop bandwidth
            info!("using 125MHz reference to make 125MHz RTIO clock with PLL");
            (
                si5324::FrequencySettings {
                    n1_hs  : 5,
                    nc1_ls : 8,
                    n2_hs  : 7,
                    n2_ls  : 360,
                    n31    : 63,
                    n32    : 63,
                    bwsel  : 4,
                    crystal_as_ckin2: false
                },
                SI5324_EXT_INPUT
            )
        },
        RtioClock::Int_100 => { // 100MHz output, from crystal
            info!("using internal 100MHz RTIO clock");
            (
                si5324::FrequencySettings {
                    n1_hs  : 9,
                    nc1_ls : 6,
                    n2_hs  : 10,
                    n2_ls  : 33732,
                    n31    : 7139,
                    n32    : 7139,
                    bwsel  : 3,
                    crystal_as_ckin2: true
                },
                si5324::Input::Ckin2
            )
        },
        RtioClock::Int_125 => { // 125MHz output, from crystal, 7 Hz
            info!("using internal 125MHz RTIO clock");
            (
                si5324::FrequencySettings {
                    n1_hs  : 10,
                    nc1_ls : 4,
                    n2_hs  : 10,
                    n2_ls  : 19972,
                    n31    : 4565,
                    n32    : 4565,
                    bwsel  : 4,
                    crystal_as_ckin2: true
                },
                si5324::Input::Ckin2
            )
        },
        _ => { // 125MHz output like above, default (if chosen option is not supported)
            warn!("rtio_clock setting '{:?}' is not supported. Falling back to default internal 125MHz RTIO clock.", cfg);
            (
                si5324::FrequencySettings {
                    n1_hs  : 10,
                    nc1_ls : 4,
                    n2_hs  : 10,
                    n2_ls  : 19972,
                    n31    : 4565,
                    n32    : 4565,
                    bwsel  : 4,
                    crystal_as_ckin2: true
                },
                si5324::Input::Ckin2
            )
        }
    };
    si5324::setup(&si5324_settings, si5324_ref_input).expect("cannot initialize Si5324");
}

fn setup_si5324(clock_cfg: RtioClock) {
    let switched = unsafe {
        csr::crg::switch_done_read()
    };
    if switched == 1 {
        info!("Clocking has already been set up.");
        return;
    }
    match clock_cfg {
        RtioClock::Ext0_Bypass => {
            info!("using external RTIO clock with PLL bypass");
            si5324::bypass(SI5324_EXT_INPUT).expect("cannot bypass Si5324")
        },
        _ => setup_si5324_as_synthesizer(clock_cfg),
    }

    // switch sysclk source to si5324
    #[cfg(not(has_drtio))]
    {
        info!("Switching sys clock, rebooting...");
        // delay for clean UART log, wait until UART FIFO is empty
        clock::spin_us(1300); 
        unsafe {
            csr::crg::clock_sel_write(1);
            loop {}
        }
    }
}


pub fn init() {
    let clock_cfg = get_rtio_clock_cfg();
    setup_si5324(clock_cfg);

    #[cfg(has_drtio)]
    {
        let switched = unsafe {
            csr::crg::switch_done_read()
        };
        if switched == 0 {
            info!("Switching sys clock, rebooting...");
            clock::spin_us(500); // delay for clean UART log
            unsafe {
                // clock switch and reboot will begin after TX is initialized
                // and TX will be initialized after this
                csr::drtio_transceiver::stable_clkin_write(1);
            }
            loop {}
        }
        else {
            // enable TX after the reboot, with stable clock
            unsafe {
                csr::drtio_transceiver::txenable_write(0xffffffffu32 as _);
            }
        }
    }


    #[cfg(has_rtio_crg)]
    {
        let result = crg::init();
        if !result {
            error!("RTIO clock failed");
        }
    }
}
