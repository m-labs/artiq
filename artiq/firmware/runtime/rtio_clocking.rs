use board_misoc::config;
#[cfg(has_si5324)]
use board_artiq::si5324;
#[cfg(has_si549)]
use board_artiq::si549;
use board_misoc::{csr, clock};

#[derive(Debug, PartialEq, Copy, Clone)]
#[allow(non_camel_case_types)]
pub enum RtioClock {
    Default,
    Int_125,
    Int_100,
    Ext0_Bypass,
    Ext0_Synth0_10to125,
    Ext0_Synth0_80to125,
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
            Ok("ext0_synth0_80to125") => RtioClock::Ext0_Synth0_80to125,
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
            #[cfg(all(rtio_frequency = "125.0", si5324_ext_ref, ext_ref_frequency = "80.0"))]
            return RtioClock::Ext0_Synth0_80to125;
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
#[cfg(all(has_si5324, soc_platform = "kasli", hw_rev = "v2.0"))]
const SI5324_EXT_INPUT: si5324::Input = si5324::Input::Ckin1;
#[cfg(all(has_si5324, soc_platform = "kasli", not(hw_rev = "v2.0")))]
const SI5324_EXT_INPUT: si5324::Input = si5324::Input::Ckin2;
#[cfg(all(has_si5324, soc_platform = "kc705"))]
const SI5324_EXT_INPUT: si5324::Input = si5324::Input::Ckin2;

#[cfg(has_si5324)]
fn setup_si5324_pll(cfg: RtioClock) {
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
        RtioClock::Ext0_Synth0_80to125 => { // 125 MHz output from 80 MHz CLKINx reference, 611 Hz BW
        info!("using 80MHz reference to make 125MHz RTIO clock with PLL");
            (
                si5324::FrequencySettings {
                    n1_hs  : 4,
                    nc1_ls : 10,
                    n2_hs  : 10,
                    n2_ls  : 250,
                    n31    : 40,
                    n32    : 40,
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

fn sysclk_setup(clock_cfg: RtioClock) {
    let switched = unsafe {
        csr::crg::switch_done_read()
    };
    if switched == 1 {
        info!("Clocking has already been set up.");
        return;
    }

    #[cfg(has_si5324)]
    match clock_cfg {
        RtioClock::Ext0_Bypass => {
            info!("using external RTIO clock with PLL bypass");
            si5324::bypass(SI5324_EXT_INPUT).expect("cannot bypass Si5324")
        },
        _ => setup_si5324_pll(clock_cfg),
    }

    #[cfg(has_si549)]
    si549::main_setup(&get_si549_setting(clock_cfg)).expect("cannot initialize main Si549");

    // switch sysclk source
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


#[cfg(all(has_si549, has_wrpll))]
fn wrpll_setup(clk: RtioClock, si549_settings: &si549::FrequencySetting) {
    // register values are directly copied from preconfigured mmcm
    let (mmcm_setting, mmcm_bypass) = match clk {
        RtioClock::Ext0_Synth0_10to125 => (
            si549::wrpll_refclk::MmcmSetting {
                // CLKFBOUT_MULT = 62.5, DIVCLK_DIVIDE = 1 , CLKOUT0_DIVIDE = 5
                clkout0_reg1: 0x1083,
                clkout0_reg2: 0x0080,
                clkfbout_reg1: 0x179e,
                clkfbout_reg2: 0x4c00,
                div_reg: 0x1041,
                lock_reg1: 0x00fa,
                lock_reg2: 0x7c01,
                lock_reg3: 0xffe9,
                power_reg: 0x9900,
                filt_reg1: 0x1008,
                filt_reg2: 0x8800,
            },
            false,
        ),
        RtioClock::Ext0_Synth0_80to125 => (
            si549::wrpll_refclk::MmcmSetting {
                // CLKFBOUT_MULT = 15.625, DIVCLK_DIVIDE = 1 , CLKOUT0_DIVIDE = 10
                clkout0_reg1: 0x1145,
                clkout0_reg2: 0x0000,
                clkfbout_reg1: 0x11c7,
                clkfbout_reg2: 0x5880,
                div_reg: 0x1041,
                lock_reg1: 0x028a,
                lock_reg2: 0x7c01,
                lock_reg3: 0xffe9,
                power_reg: 0x9900,
                filt_reg1: 0x9908,
                filt_reg2: 0x8100,
            },
            false,
        ),
        RtioClock::Ext0_Synth0_100to125 => (
            si549::wrpll_refclk::MmcmSetting {
                // CLKFBOUT_MULT = 12.5, DIVCLK_DIVIDE = 1 , CLKOUT0_DIVIDE = 10
                clkout0_reg1: 0x1145,
                clkout0_reg2: 0x0000,
                clkfbout_reg1: 0x1145,
                clkfbout_reg2: 0x4c00,
                div_reg: 0x1041,
                lock_reg1: 0x0339,
                lock_reg2: 0x7c01,
                lock_reg3: 0xffe9,
                power_reg: 0x9900,
                filt_reg1: 0x9108,
                filt_reg2: 0x0100,
            },
            false,
        ),
        RtioClock::Ext0_Synth0_125to125 => (
            si549::wrpll_refclk::MmcmSetting {
                // CLKFBOUT_MULT = 10, DIVCLK_DIVIDE = 1 , CLKOUT0_DIVIDE = 10
                clkout0_reg1: 0x1145,
                clkout0_reg2: 0x0000,
                clkfbout_reg1: 0x1145,
                clkfbout_reg2: 0x0000,
                div_reg: 0x1041,
                lock_reg1: 0x03e8,
                lock_reg2: 0x7001,
                lock_reg3: 0xf3e9,
                power_reg: 0x0100,
                filt_reg1: 0x9908,
                filt_reg2: 0x1100,
            },
            true,
        ),
        _ => unreachable!(),
    };

    si549::helper_setup(&si549_settings).expect("cannot initialize helper Si549");
    si549::wrpll_refclk::setup(mmcm_setting, mmcm_bypass).expect("cannot initialize ref clk for wrpll");
    si549::wrpll::select_recovered_clock(true);
}

#[cfg(has_si549)]
fn get_si549_setting(clk: RtioClock) -> si549::FrequencySetting {
    match clk {
        RtioClock::Ext0_Synth0_10to125 => {
            info!("using 10MHz reference to make 125MHz RTIO clock with WRPLL");
        }
        RtioClock::Ext0_Synth0_80to125 => {
            info!("using 80MHz reference to make 125MHz RTIO clock with WRPLL");
        }
        RtioClock::Ext0_Synth0_100to125 => {
            info!("using 100MHz reference to make 125MHz RTIO clock with WRPLL");
        }
        RtioClock::Ext0_Synth0_125to125 => {
            info!("using 125MHz reference to make 125MHz RTIO clock with WRPLL");
        }
        RtioClock::Int_100 => {
            info!("using internal 100MHz RTIO clock");
        }
        RtioClock::Int_125 => {
            info!("using internal 125MHz RTIO clock");
        }
        _ => {
            warn!(
                "rtio_clock setting '{:?}' is unsupported. Falling back to default internal 125MHz RTIO clock.",
                clk
            );
        }
    };

    match clk {
        RtioClock::Int_100 => {
            si549::FrequencySetting {
                main: si549::DividerConfig {
                    hsdiv: 0x06C,
                    lsdiv: 0,
                    fbdiv: 0x046C5F49797,
                },
                helper: si549::DividerConfig {
                    // 100MHz*32767/32768
                    hsdiv: 0x06C,
                    lsdiv: 0,
                    fbdiv: 0x046C5670BBD,
                },
            }
        }
        _ => {
            // Everything else use 125MHz
            si549::FrequencySetting {
                main: si549::DividerConfig {
                    hsdiv: 0x058,
                    lsdiv: 0,
                    fbdiv: 0x04815791F25,
                },
                helper: si549::DividerConfig {
                    // 125MHz*32767/32768
                    hsdiv: 0x058,
                    lsdiv: 0,
                    fbdiv: 0x04814E8F442,
                },
            }
        }
    }
}

pub fn init() {
    let clock_cfg = get_rtio_clock_cfg();
    sysclk_setup(clock_cfg);

    #[cfg(has_drtio)]
    {
        let switched = unsafe {
            csr::crg::switch_done_read()
        };
        if switched == 0 {
            info!("Switching sys clock, rebooting...");
            clock::spin_us(3000); // delay for clean UART log
            unsafe {
                // clock switch and reboot will begin after TX is initialized
                // and TX will be initialized after this
                csr::gt_drtio::stable_clkin_write(1);
            }
            loop {}
        }
        else {
            // enable TX after the reboot, with stable clock
            unsafe {
                csr::gt_drtio::txenable_write(0xffffffffu32 as _);

                #[cfg(has_drtio_eem)]
                csr::eem_transceiver::txenable_write(0xffffffffu32 as _);
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

    #[cfg(all(has_si549, has_wrpll))]
    {
        // SYS CLK switch will reset CSRs that are used by WRPLL
        match clock_cfg {
            RtioClock::Ext0_Synth0_10to125
            | RtioClock::Ext0_Synth0_80to125
            | RtioClock::Ext0_Synth0_100to125
            | RtioClock::Ext0_Synth0_125to125 => {
                wrpll_setup(clock_cfg, &get_si549_setting(clock_cfg));
            }
            _ => {}
        }
    }
}
