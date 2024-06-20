use board_misoc::{clock, csr};
use log::info;

const ADDRESS: u8 = 0x67;

const ADPLL_MAX: i32 = (950.0 / 0.0001164) as i32;

pub struct DividerConfig {
    pub hsdiv: u16,
    pub lsdiv: u8,
    pub fbdiv: u64,
}

pub struct FrequencySetting {
    pub main: DividerConfig,
    pub helper: DividerConfig,
}

mod i2c {
    use super::*;

    #[derive(Clone, Copy)]
    pub enum DCXO {
        Main,
        Helper,
    }

    fn half_period() {
        clock::spin_us(1)
    }

    fn sda_i(dcxo: DCXO) -> bool {
        match dcxo {
            DCXO::Main => unsafe { csr::wrpll::main_dcxo_sda_in_read() == 1 },
            DCXO::Helper => unsafe { csr::wrpll::helper_dcxo_sda_in_read() == 1 },
        }
    }

    fn sda_oe(dcxo: DCXO, oe: bool) {
        let val = if oe { 1 } else { 0 };
        match dcxo {
            DCXO::Main => unsafe { csr::wrpll::main_dcxo_sda_oe_write(val) },
            DCXO::Helper => unsafe { csr::wrpll::helper_dcxo_sda_oe_write(val) },
        };
    }

    fn sda_o(dcxo: DCXO, o: bool) {
        let val = if o { 1 } else { 0 };
        match dcxo {
            DCXO::Main => unsafe { csr::wrpll::main_dcxo_sda_out_write(val) },
            DCXO::Helper => unsafe { csr::wrpll::helper_dcxo_sda_out_write(val) },
        };
    }

    fn scl_oe(dcxo: DCXO, oe: bool) {
        let val = if oe { 1 } else { 0 };
        match dcxo {
            DCXO::Main => unsafe { csr::wrpll::main_dcxo_scl_oe_write(val) },
            DCXO::Helper => unsafe { csr::wrpll::helper_dcxo_scl_oe_write(val) },
        };
    }

    fn scl_o(dcxo: DCXO, o: bool) {
        let val = if o { 1 } else { 0 };
        match dcxo {
            DCXO::Main => unsafe { csr::wrpll::main_dcxo_scl_out_write(val) },
            DCXO::Helper => unsafe { csr::wrpll::helper_dcxo_scl_out_write(val) },
        };
    }

    pub fn init(dcxo: DCXO) -> Result<(), &'static str> {
        // Set SCL as output, and high level
        scl_o(dcxo, true);
        scl_oe(dcxo, true);
        // Prepare a zero level on SDA so that sda_oe pulls it down
        sda_o(dcxo, false);
        // Release SDA
        sda_oe(dcxo, false);

        // Check the I2C bus is ready
        half_period();
        half_period();
        if !sda_i(dcxo) {
            // Try toggling SCL a few times
            for _bit in 0..8 {
                scl_o(dcxo, false);
                half_period();
                scl_o(dcxo, true);
                half_period();
            }
        }

        if !sda_i(dcxo) {
            return Err("SDA is stuck low and doesn't get unstuck");
        }
        Ok(())
    }

    pub fn start(dcxo: DCXO) {
        // Set SCL high then SDA low
        scl_o(dcxo, true);
        half_period();
        sda_oe(dcxo, true);
        half_period();
    }

    pub fn stop(dcxo: DCXO) {
        // First, make sure SCL is low, so that the target releases the SDA line
        scl_o(dcxo, false);
        half_period();
        // Set SCL high then SDA high
        sda_oe(dcxo, true);
        scl_o(dcxo, true);
        half_period();
        sda_oe(dcxo, false);
        half_period();
    }

    pub fn write(dcxo: DCXO, data: u8) -> bool {
        // MSB first
        for bit in (0..8).rev() {
            // Set SCL low and set our bit on SDA
            scl_o(dcxo, false);
            sda_oe(dcxo, data & (1 << bit) == 0);
            half_period();
            // Set SCL high ; data is shifted on the rising edge of SCL
            scl_o(dcxo, true);
            half_period();
        }
        // Check ack
        // Set SCL low, then release SDA so that the I2C target can respond
        scl_o(dcxo, false);
        half_period();
        sda_oe(dcxo, false);
        // Set SCL high and check for ack
        scl_o(dcxo, true);
        half_period();
        // returns true if acked (I2C target pulled SDA low)
        !sda_i(dcxo)
    }

    pub fn read(dcxo: DCXO, ack: bool) -> u8 {
        // Set SCL low first, otherwise setting SDA as input may cause a transition
        // on SDA with SCL high which will be interpreted as START/STOP condition.
        scl_o(dcxo, false);
        half_period(); // make sure SCL has settled low
        sda_oe(dcxo, false);

        let mut data: u8 = 0;

        // MSB first
        for bit in (0..8).rev() {
            scl_o(dcxo, false);
            half_period();
            // Set SCL high and shift data
            scl_o(dcxo, true);
            half_period();
            if sda_i(dcxo) {
                data |= 1 << bit
            }
        }
        // Send ack
        // Set SCL low and pull SDA low when acking
        scl_o(dcxo, false);
        if ack {
            sda_oe(dcxo, true)
        }
        half_period();
        // then set SCL high
        scl_o(dcxo, true);
        half_period();

        data
    }
}

fn write(dcxo: i2c::DCXO, reg: u8, val: u8) -> Result<(), &'static str> {
    i2c::start(dcxo);
    if !i2c::write(dcxo, ADDRESS << 1) {
        return Err("Si549 failed to ack write address");
    }
    if !i2c::write(dcxo, reg) {
        return Err("Si549 failed to ack register");
    }
    if !i2c::write(dcxo, val) {
        return Err("Si549 failed to ack value");
    }
    i2c::stop(dcxo);
    Ok(())
}

fn read(dcxo: i2c::DCXO, reg: u8) -> Result<u8, &'static str> {
    i2c::start(dcxo);
    if !i2c::write(dcxo, ADDRESS << 1) {
        return Err("Si549 failed to ack write address");
    }
    if !i2c::write(dcxo, reg) {
        return Err("Si549 failed to ack register");
    }
    i2c::stop(dcxo);

    i2c::start(dcxo);
    if !i2c::write(dcxo, (ADDRESS << 1) | 1) {
        return Err("Si549 failed to ack read address");
    }
    let val = i2c::read(dcxo, false);
    i2c::stop(dcxo);
    Ok(val)
}

fn setup(dcxo: i2c::DCXO, config: &DividerConfig) -> Result<(), &'static str> {
    i2c::init(dcxo)?;

    write(dcxo, 255, 0x00)?; // PAGE
    write(dcxo, 69, 0x00)?; // Disable FCAL override.
    write(dcxo, 17, 0x00)?; // Synchronously disable output

    // The Si549 has no ID register, so we check that it responds correctly
    // by writing values to a RAM-like register and reading them back.
    for test_value in 0..255 {
        write(dcxo, 23, test_value)?;
        let readback = read(dcxo, 23)?;
        if readback != test_value {
            return Err("Si549 detection failed");
        }
    }

    write(dcxo, 23, config.hsdiv as u8)?;
    write(dcxo, 24, (config.hsdiv >> 8) as u8 | (config.lsdiv << 4))?;
    write(dcxo, 26, config.fbdiv as u8)?;
    write(dcxo, 27, (config.fbdiv >> 8) as u8)?;
    write(dcxo, 28, (config.fbdiv >> 16) as u8)?;
    write(dcxo, 29, (config.fbdiv >> 24) as u8)?;
    write(dcxo, 30, (config.fbdiv >> 32) as u8)?;
    write(dcxo, 31, (config.fbdiv >> 40) as u8)?;

    write(dcxo, 7, 0x08)?; // Start FCAL
    clock::spin_us(30_000); // Internal FCAL VCO calibration
    write(dcxo, 17, 0x01)?; // Synchronously enable output

    Ok(())
}

pub fn main_setup(settings: &FrequencySetting) -> Result<(), &'static str> {
    unsafe {
        csr::wrpll::main_dcxo_bitbang_enable_write(1);
        csr::wrpll::main_dcxo_i2c_address_write(ADDRESS);
    }

    setup(i2c::DCXO::Main, &settings.main)?;

    // Si549 maximum settling time for large frequency change.
    clock::spin_us(40_000);

    unsafe {
        csr::wrpll::main_dcxo_bitbang_enable_write(0);
    }

    info!("Main Si549 started");
    Ok(())
}

pub fn helper_setup(settings: &FrequencySetting) -> Result<(), &'static str> {
    unsafe {
        csr::wrpll::helper_reset_write(1);
        csr::wrpll::helper_dcxo_bitbang_enable_write(1);
        csr::wrpll::helper_dcxo_i2c_address_write(ADDRESS);
    }

    setup(i2c::DCXO::Helper, &settings.helper)?;

    // Si549 maximum settling time for large frequency change.
    clock::spin_us(40_000);

    unsafe {
        csr::wrpll::helper_reset_write(0);
        csr::wrpll::helper_dcxo_bitbang_enable_write(0);
    }
    info!("Helper Si549 started");
    Ok(())
}

fn set_adpll(dcxo: i2c::DCXO, adpll: i32) -> Result<(), &'static str> {
    if adpll.abs() > ADPLL_MAX {
        return Err("adpll is too large");
    }

    match dcxo {
        i2c::DCXO::Main => unsafe {
            if csr::wrpll::main_dcxo_bitbang_enable_read() == 1 {
                return Err("Main si549 bitbang mode is active when using gateware i2c");
            }

            while csr::wrpll::main_dcxo_adpll_busy_read() == 1 {}
            if csr::wrpll::main_dcxo_nack_read() == 1 {
                return Err("Main si549 failed to ack adpll write");
            }

            csr::wrpll::main_dcxo_i2c_address_write(ADDRESS);
            csr::wrpll::main_dcxo_adpll_write(adpll as u32);

            csr::wrpll::main_dcxo_adpll_stb_write(1);
        },
        i2c::DCXO::Helper => unsafe {
            if csr::wrpll::helper_dcxo_bitbang_enable_read() == 1 {
                return Err("Helper si549 bitbang mode is active when using gateware i2c");
            }

            while csr::wrpll::helper_dcxo_adpll_busy_read() == 1 {}
            if csr::wrpll::helper_dcxo_nack_read() == 1 {
                return Err("Helper si549 failed to ack adpll write");
            }

            csr::wrpll::helper_dcxo_i2c_address_write(ADDRESS);
            csr::wrpll::helper_dcxo_adpll_write(adpll as u32);

            csr::wrpll::helper_dcxo_adpll_stb_write(1);
        },
    };

    Ok(())
}

#[cfg(has_wrpll)]
pub mod wrpll {

    use super::*;

    const BEATING_PERIOD: i32 = 0x8000;
    const BEATING_HALFPERIOD: i32 = 0x4000;
    const COUNTER_WIDTH: u32 = 24;
    const DIV_WIDTH: u32 = 2;

    // y[n] = b0*x[n] + b1*x[n-1] + b2*x[n-2] - a1*y[n-1] - a2*y[n-2]
    struct FilterParameters {
        pub b0: i64,
        pub b1: i64,
        pub b2: i64,
        pub a1: i64,
        pub a2: i64,
    }

    #[cfg(rtio_frequency = "100.0")]
    const LPF: FilterParameters = FilterParameters {
        b0: 10905723400,   // 0.03967479060647884 * 1 << 38
        b1: 21811446800,   // 0.07934958121295768 * 1 << 38
        b2: 10905723400,   // 0.03967479060647884 * 1 << 38
        a1: -381134538612, // -1.3865593741228928 * 1 << 38
        a2: 149879525269,  // 0.5452585365488082  * 1 << 38
    };

    #[cfg(rtio_frequency = "125.0")]
    const LPF: FilterParameters = FilterParameters {
        b0: 19816511911,   // 0.07209205036273991  * 1 << 38
        b1: 39633023822,   // 0.14418410072547982  * 1 << 38
        b2: 19816511911,   // 0.07209205036273991  * 1 << 38
        a1: -168062510414, // -0.6114078511562919  * 1 << 38
        a2: -27549348884,  // -0.10022394739274834 * 1 << 38
    };

    static mut H_ADPLL1: i32 = 0;
    static mut H_ADPLL2: i32 = 0;
    static mut PERIOD_ERR1: i32 = 0;
    static mut PERIOD_ERR2: i32 = 0;

    static mut M_ADPLL1: i32 = 0;
    static mut M_ADPLL2: i32 = 0;
    static mut PHASE_ERR1: i32 = 0;
    static mut PHASE_ERR2: i32 = 0;

    static mut BASE_ADPLL: i32 = 0;

    #[derive(Clone, Copy)]
    pub enum ISR {
        RefTag,
        MainTag,
    }

    mod tag_collector {
        use super::*;

        #[cfg(wrpll_ref_clk = "GT_CDR")]
        static mut TAG_OFFSET: u32 = 23890;
        #[cfg(wrpll_ref_clk = "SMA_CLKIN")]
        static mut TAG_OFFSET: u32 = 0;
        static mut REF_TAG: u32 = 0;
        static mut REF_TAG_READY: bool = false;
        static mut MAIN_TAG: u32 = 0;
        static mut MAIN_TAG_READY: bool = false;

        pub fn reset() {
            clear_phase_diff_ready();
            unsafe {
                REF_TAG = 0;
                MAIN_TAG = 0;
            }
        }

        pub fn clear_phase_diff_ready() {
            unsafe {
                REF_TAG_READY = false;
                MAIN_TAG_READY = false;
            }
        }

        pub fn collect_tags(interrupt: ISR) {
            match interrupt {
                ISR::RefTag => unsafe {
                    REF_TAG = csr::wrpll::ref_tag_read();
                    REF_TAG_READY = true;
                },
                ISR::MainTag => unsafe {
                    MAIN_TAG = csr::wrpll::main_tag_read();
                    MAIN_TAG_READY = true;
                },
            }
        }

        pub fn phase_diff_ready() -> bool {
            unsafe { REF_TAG_READY && MAIN_TAG_READY }
        }

        #[cfg(feature = "calibrate_wrpll_skew")]
        pub fn set_tag_offset(offset: u32) {
            unsafe {
                TAG_OFFSET = offset;
            }
        }

        #[cfg(feature = "calibrate_wrpll_skew")]
        pub fn get_tag_offset() -> u32 {
            unsafe { TAG_OFFSET }
        }

        pub fn get_period_error() -> i32 {
            // n * BEATING_PERIOD - REF_TAG(n) mod BEATING_PERIOD
            let mut period_error = unsafe {
                REF_TAG
                    .overflowing_neg()
                    .0
                    .rem_euclid(BEATING_PERIOD as u32) as i32
            };
            // mapping tags from [0, 2π] -> [-π, π]
            if period_error > BEATING_HALFPERIOD {
                period_error -= BEATING_PERIOD
            }
            period_error
        }

        pub fn get_phase_error() -> i32 {
            // MAIN_TAG(n) - REF_TAG(n) - TAG_OFFSET mod BEATING_PERIOD
            let mut phase_error = unsafe {
                MAIN_TAG
                    .overflowing_sub(REF_TAG + TAG_OFFSET)
                    .0
                    .rem_euclid(BEATING_PERIOD as u32) as i32
            };

            // mapping tags from [0, 2π] -> [-π, π]
            if phase_error > BEATING_HALFPERIOD {
                phase_error -= BEATING_PERIOD
            }
            phase_error
        }
    }

    fn set_isr(en: bool) {
        let val = if en { 1 } else { 0 };
        unsafe {
            csr::wrpll::ref_tag_ev_enable_write(val);
            csr::wrpll::main_tag_ev_enable_write(val);
        }
    }

    fn set_base_adpll() -> Result<(), &'static str> {
        let count2adpll = |error: i32| {
            ((error as f64 * 1e6) / (0.0001164 * (1 << (COUNTER_WIDTH - DIV_WIDTH)) as f64)) as i32
        };

        let (ref_count, main_count) = get_freq_counts();
        unsafe {
            BASE_ADPLL = count2adpll(ref_count as i32 - main_count as i32);
            set_adpll(i2c::DCXO::Main, BASE_ADPLL)?;
            set_adpll(i2c::DCXO::Helper, BASE_ADPLL)?;
        }
        Ok(())
    }

    fn get_freq_counts() -> (u32, u32) {
        unsafe {
            csr::wrpll::frequency_counter_update_write(1);
            while csr::wrpll::frequency_counter_busy_read() == 1 {}
            #[cfg(wrpll_ref_clk = "GT_CDR")]
            let ref_count = csr::wrpll::frequency_counter_counter_rtio_rx0_read();
            #[cfg(wrpll_ref_clk = "SMA_CLKIN")]
            let ref_count = csr::wrpll::frequency_counter_counter_ref_read();
            let main_count = csr::wrpll::frequency_counter_counter_sys_read();

            (ref_count, main_count)
        }
    }

    fn reset_plls() -> Result<(), &'static str> {
        unsafe {
            H_ADPLL1 = 0;
            H_ADPLL2 = 0;
            PERIOD_ERR1 = 0;
            PERIOD_ERR2 = 0;
            M_ADPLL1 = 0;
            M_ADPLL2 = 0;
            PHASE_ERR1 = 0;
            PHASE_ERR2 = 0;
        }
        set_adpll(i2c::DCXO::Main, 0)?;
        set_adpll(i2c::DCXO::Helper, 0)?;
        // wait for adpll to transfer and DCXO to settle
        clock::spin_us(200);
        Ok(())
    }

    fn clear_pending(interrupt: ISR) {
        match interrupt {
            ISR::RefTag => unsafe { csr::wrpll::ref_tag_ev_pending_write(1) },
            ISR::MainTag => unsafe { csr::wrpll::main_tag_ev_pending_write(1) },
        };
    }

    fn is_pending(interrupt: ISR) -> bool {
        match interrupt {
            ISR::RefTag => unsafe { csr::wrpll::ref_tag_ev_pending_read() == 1 },
            ISR::MainTag => unsafe { csr::wrpll::main_tag_ev_pending_read() == 1 },
        }
    }

    pub fn interrupt_handler() {
        if is_pending(ISR::RefTag) {
            tag_collector::collect_tags(ISR::RefTag);
            clear_pending(ISR::RefTag);
            helper_pll().expect("failed to run helper DCXO PLL");
        }

        if is_pending(ISR::MainTag) {
            tag_collector::collect_tags(ISR::MainTag);
            clear_pending(ISR::MainTag);
        }

        if tag_collector::phase_diff_ready() {
            main_pll().expect("failed to run main DCXO PLL");
            tag_collector::clear_phase_diff_ready();
        }
    }

    fn helper_pll() -> Result<(), &'static str> {
        let period_err = tag_collector::get_period_error();
        unsafe {
            let adpll = (((LPF.b0 * period_err as i64)
                + (LPF.b1 * PERIOD_ERR1 as i64)
                + (LPF.b2 * PERIOD_ERR2 as i64)
                - (LPF.a1 * H_ADPLL1 as i64)
                - (LPF.a2 * H_ADPLL2 as i64))
                >> 38) as i32;
            set_adpll(i2c::DCXO::Helper, BASE_ADPLL + adpll)?;
            H_ADPLL2 = H_ADPLL1;
            PERIOD_ERR2 = PERIOD_ERR1;
            H_ADPLL1 = adpll;
            PERIOD_ERR1 = period_err;
        };
        Ok(())
    }

    fn main_pll() -> Result<(), &'static str> {
        let phase_err = tag_collector::get_phase_error();
        unsafe {
            let adpll = (((LPF.b0 * phase_err as i64)
                + (LPF.b1 * PHASE_ERR1 as i64)
                + (LPF.b2 * PHASE_ERR2 as i64)
                - (LPF.a1 * M_ADPLL1 as i64)
                - (LPF.a2 * M_ADPLL2 as i64))
                >> 38) as i32;
            set_adpll(i2c::DCXO::Main, BASE_ADPLL + adpll)?;
            M_ADPLL2 = M_ADPLL1;
            PHASE_ERR2 = PHASE_ERR1;
            M_ADPLL1 = adpll;
            PHASE_ERR1 = phase_err;
        };
        Ok(())
    }

    #[cfg(wrpll_ref_clk = "GT_CDR")]
    fn test_skew() -> Result<(), &'static str> {
        // wait for PLL to stabilize
        clock::spin_us(20_000);

        info!("testing the skew of SYS CLK...");
        if has_timing_error() {
            return Err("the skew cannot satisfy setup/hold time constraint of RX synchronizer");
        }
        info!("the skew of SYS CLK met the timing constraint");
        Ok(())
    }

    #[cfg(wrpll_ref_clk = "GT_CDR")]
    fn has_timing_error() -> bool {
        unsafe {
            csr::wrpll_skewtester::error_write(1);
        }
        clock::spin_us(5_000);
        unsafe { csr::wrpll_skewtester::error_read() == 1 }
    }

    #[cfg(feature = "calibrate_wrpll_skew")]
    fn find_edge(target: bool) -> Result<u32, &'static str> {
        const STEP: u32 = 8;
        const STABLE_THRESHOLD: u32 = 10;

        enum FSM {
            Init,
            WaitEdge,
            GotEdge,
        }

        let mut state: FSM = FSM::Init;
        let mut offset: u32 = tag_collector::get_tag_offset();
        let mut median_edge: u32 = 0;
        let mut stable_counter: u32 = 0;

        for _ in 0..(BEATING_PERIOD as u32 / STEP) as usize {
            tag_collector::set_tag_offset(offset);
            offset += STEP;
            // wait for PLL to stabilize
            clock::spin_us(20_000);

            let error = has_timing_error();
            // A median edge deglitcher
            match state {
                FSM::Init => {
                    if error != target {
                        stable_counter += 1;
                    } else {
                        stable_counter = 0;
                    }

                    if stable_counter >= STABLE_THRESHOLD {
                        state = FSM::WaitEdge;
                        stable_counter = 0;
                    }
                }
                FSM::WaitEdge => {
                    if error == target {
                        state = FSM::GotEdge;
                        median_edge = offset;
                    }
                }
                FSM::GotEdge => {
                    if error != target {
                        median_edge += STEP;
                        stable_counter = 0;
                    } else {
                        stable_counter += 1;
                    }

                    if stable_counter >= STABLE_THRESHOLD {
                        return Ok(median_edge);
                    }
                }
            }
        }
        return Err("failed to find timing error edge");
    }

    #[cfg(feature = "calibrate_wrpll_skew")]
    fn calibrate_skew() -> Result<(), &'static str> {
        info!("calibrating skew to meet timing constraint...");

        // clear calibrated value
        tag_collector::set_tag_offset(0);
        let rising = find_edge(true)? as i32;
        let falling = find_edge(false)? as i32;

        let width = BEATING_PERIOD - (falling - rising);
        let result = falling + width / 2;
        tag_collector::set_tag_offset(result as u32);

        info!(
            "calibration successful, error zone: {} -> {}, width: {} ({}deg), middle of working region: {}",
            rising,
            falling,
            width,
            360 * width / BEATING_PERIOD,
            result,
        );

        Ok(())
    }

    pub fn select_recovered_clock(rc: bool) {
        set_isr(false);

        if rc {
            tag_collector::reset();
            reset_plls().expect("failed to reset main and helper PLL");

            // get within capture range
            set_base_adpll().expect("failed to set base adpll");

            // clear gateware pending flag
            clear_pending(ISR::RefTag);
            clear_pending(ISR::MainTag);

            // use nFIQ to avoid IRQ being disabled by mutex lock and mess up PLL
            set_isr(true);
            info!("WRPLL interrupt enabled");

            #[cfg(feature = "calibrate_wrpll_skew")]
            calibrate_skew().expect("failed to set the correct skew");

            #[cfg(wrpll_ref_clk = "GT_CDR")]
            test_skew().expect("skew test failed");
        }
    }
}

#[cfg(has_wrpll_refclk)]
pub mod wrpll_refclk {
    use super::*;

    pub struct MmcmSetting {
        pub clkout0_reg1: u16,  //0x08
        pub clkout0_reg2: u16,  //0x09
        pub clkfbout_reg1: u16, //0x14
        pub clkfbout_reg2: u16, //0x15
        pub div_reg: u16,       //0x16
        pub lock_reg1: u16,     //0x18
        pub lock_reg2: u16,     //0x19
        pub lock_reg3: u16,     //0x1A
        pub power_reg: u16,     //0x28
        pub filt_reg1: u16,     //0x4E
        pub filt_reg2: u16,     //0x4F
    }

    fn one_clock_cycle() {
        unsafe {
            csr::wrpll_refclk::mmcm_dclk_write(1);
            csr::wrpll_refclk::mmcm_dclk_write(0);
        }
    }

    fn set_addr(address: u8) {
        unsafe {
            csr::wrpll_refclk::mmcm_daddr_write(address);
        }
    }

    fn set_data(value: u16) {
        unsafe {
            csr::wrpll_refclk::mmcm_din_write(value);
        }
    }

    fn set_enable(en: bool) {
        let val = if en { 1 } else { 0 };
        unsafe {
            csr::wrpll_refclk::mmcm_den_write(val);
        }
    }

    fn set_write_enable(en: bool) {
        let val = if en { 1 } else { 0 };
        unsafe {
            csr::wrpll_refclk::mmcm_dwen_write(val);
        }
    }

    fn get_data() -> u16 {
        unsafe { csr::wrpll_refclk::mmcm_dout_read() }
    }

    fn drp_ready() -> bool {
        unsafe { csr::wrpll_refclk::mmcm_dready_read() == 1 }
    }

    #[allow(dead_code)]
    fn read(address: u8) -> u16 {
        set_addr(address);
        set_enable(true);
        // Set DADDR on the mmcm and assert DEN for one clock cycle
        one_clock_cycle();

        set_enable(false);
        while !drp_ready() {
            // keep the clock signal until data is ready
            one_clock_cycle();
        }
        get_data()
    }

    fn write(address: u8, value: u16) {
        set_addr(address);
        set_data(value);
        set_write_enable(true);
        set_enable(true);
        // Set DADDR, DI on the mmcm and assert DWE, DEN for one clock cycle
        one_clock_cycle();

        set_write_enable(false);
        set_enable(false);
        while !drp_ready() {
            // keep the clock signal until write is finished
            one_clock_cycle();
        }
    }

    fn reset(rst: bool) {
        let val = if rst { 1 } else { 0 };
        unsafe {
            csr::wrpll_refclk::mmcm_reset_write(val)
        }
    }

    pub fn setup(settings: MmcmSetting, mmcm_bypass: bool) -> Result<(), &'static str> {
        unsafe {
            csr::wrpll_refclk::refclk_reset_write(1);
        }

        if mmcm_bypass {
            info!("Bypassing mmcm");
            unsafe {
                csr::wrpll_refclk::mmcm_bypass_write(1);
            }
        } else {
            // Based on "DRP State Machine" from XAPP888
            // hold reset HIGH during mmcm config
            reset(true);
            write(0x08, settings.clkout0_reg1);
            write(0x09, settings.clkout0_reg2);
            write(0x14, settings.clkfbout_reg1);
            write(0x15, settings.clkfbout_reg2);
            write(0x16, settings.div_reg);
            write(0x18, settings.lock_reg1);
            write(0x19, settings.lock_reg2);
            write(0x1A, settings.lock_reg3);
            write(0x28, settings.power_reg);
            write(0x4E, settings.filt_reg1);
            write(0x4F, settings.filt_reg2);
            reset(false);

            // wait for the mmcm to lock
            clock::spin_us(100);

            let locked = unsafe { csr::wrpll_refclk::mmcm_locked_read() == 1 };
            if !locked {
                return Err("mmcm failed to generate 125MHz ref clock from SMA CLKIN");
            }
        }

        unsafe {
            csr::wrpll_refclk::refclk_reset_write(0);
        }

        Ok(())
    }
}
