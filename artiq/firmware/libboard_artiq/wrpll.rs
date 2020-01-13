use board_misoc::{csr, clock};

mod i2c {
    use board_misoc::{csr, clock};

    #[derive(Debug, Clone, Copy)]
    pub enum Dcxo {
        Main,
        Helper
    }

    fn half_period() { clock::spin_us(1) }
    const SDA_MASK: u8 = 2;
    const SCL_MASK: u8 = 1;

    fn sda_i(dcxo: Dcxo) -> bool {
        let reg = match dcxo {
            Dcxo::Main => unsafe { csr::wrpll::main_dcxo_gpio_in_read() },
            Dcxo::Helper => unsafe { csr::wrpll::helper_dcxo_gpio_in_read() },
        };
        reg & SDA_MASK != 0
    }

    fn sda_oe(dcxo: Dcxo, oe: bool) {
        let reg = match dcxo {
            Dcxo::Main => unsafe { csr::wrpll::main_dcxo_gpio_oe_read() },
            Dcxo::Helper => unsafe { csr::wrpll::helper_dcxo_gpio_oe_read() },
        };
        let reg = if oe { reg | SDA_MASK } else { reg & !SDA_MASK };
        match dcxo {
            Dcxo::Main => unsafe { csr::wrpll::main_dcxo_gpio_oe_write(reg) },
            Dcxo::Helper => unsafe { csr::wrpll::helper_dcxo_gpio_oe_write(reg) }
        }
    }

    fn sda_o(dcxo: Dcxo, o: bool) {
        let reg = match dcxo {
            Dcxo::Main => unsafe { csr::wrpll::main_dcxo_gpio_out_read() },
            Dcxo::Helper => unsafe { csr::wrpll::helper_dcxo_gpio_out_read() },
        };
        let reg = if o  { reg | SDA_MASK } else { reg & !SDA_MASK };
        match dcxo {
            Dcxo::Main => unsafe { csr::wrpll::main_dcxo_gpio_out_write(reg) },
            Dcxo::Helper => unsafe { csr::wrpll::helper_dcxo_gpio_out_write(reg) }
        }
    }

    fn scl_oe(dcxo: Dcxo, oe: bool) {
        let reg = match dcxo {
            Dcxo::Main => unsafe { csr::wrpll::main_dcxo_gpio_oe_read() },
            Dcxo::Helper => unsafe { csr::wrpll::helper_dcxo_gpio_oe_read() },
        };
        let reg = if oe { reg | SCL_MASK } else { reg & !SCL_MASK };
        match dcxo {
            Dcxo::Main => unsafe { csr::wrpll::main_dcxo_gpio_oe_write(reg) },
            Dcxo::Helper => unsafe { csr::wrpll::helper_dcxo_gpio_oe_write(reg) }
        }
    }

    fn scl_o(dcxo: Dcxo, o: bool) {
        let reg = match dcxo {
            Dcxo::Main => unsafe { csr::wrpll::main_dcxo_gpio_out_read() },
            Dcxo::Helper => unsafe { csr::wrpll::helper_dcxo_gpio_out_read() },
        };
        let reg = if o  { reg | SCL_MASK } else { reg & !SCL_MASK };
        match dcxo {
            Dcxo::Main => unsafe { csr::wrpll::main_dcxo_gpio_out_write(reg) },
            Dcxo::Helper => unsafe { csr::wrpll::helper_dcxo_gpio_out_write(reg) }
        }
    }

    pub fn init(dcxo: Dcxo) -> Result<(), &'static str> {
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

    pub fn start(dcxo: Dcxo) {
        // Set SCL high then SDA low
        scl_o(dcxo, true);
        half_period();
        sda_oe(dcxo, true);
        half_period();
    }

    pub fn stop(dcxo: Dcxo) {
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

    pub fn write(dcxo: Dcxo, data: u8) -> bool {
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

    pub fn read(dcxo: Dcxo, ack: bool) -> u8 {
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
            if sda_i(dcxo) { data |= 1 << bit }
        }
        // Send ack
        // Set SCL low and pull SDA low when acking
        scl_o(dcxo, false);
        if ack { sda_oe(dcxo, true) }
        half_period();
        // then set SCL high
        scl_o(dcxo, true);
        half_period();

        data
    }
}

mod si549 {
    use board_misoc::clock;
    use super::i2c;

    pub const ADDRESS: u8 = 0x55;

    pub fn write(dcxo: i2c::Dcxo, reg: u8, val: u8) -> Result<(), &'static str> {
        i2c::start(dcxo);
        if !i2c::write(dcxo, ADDRESS << 1) {
            return Err("Si549 failed to ack write address")
        }
        if !i2c::write(dcxo, reg) {
            return Err("Si549 failed to ack register")
        }
        if !i2c::write(dcxo, val) {
            return Err("Si549 failed to ack value")
        }
        i2c::stop(dcxo);
        Ok(())
    }

    pub fn write_no_ack_value(dcxo: i2c::Dcxo, reg: u8, val: u8) -> Result<(), &'static str> {
        i2c::start(dcxo);
        if !i2c::write(dcxo, ADDRESS << 1) {
            return Err("Si549 failed to ack write address")
        }
        if !i2c::write(dcxo, reg) {
            return Err("Si549 failed to ack register")
        }
        i2c::write(dcxo, val);
        i2c::stop(dcxo);
        Ok(())
    }

    pub fn read(dcxo: i2c::Dcxo, reg: u8) -> Result<u8, &'static str> {
        i2c::start(dcxo);
        if !i2c::write(dcxo, ADDRESS << 1) {
            return Err("Si549 failed to ack write address")
        }
        if !i2c::write(dcxo, reg) {
            return Err("Si549 failed to ack register")
        }
        i2c::stop(dcxo);

        i2c::start(dcxo);
        if !i2c::write(dcxo, (ADDRESS << 1) | 1) {
            return Err("Si549 failed to ack read address")
        }
        let val = i2c::read(dcxo, false);
        i2c::stop(dcxo);

        Ok(val)
    }

    pub fn program(dcxo: i2c::Dcxo, hsdiv: u16, lsdiv: u8, fbdiv: u64) -> Result<(), &'static str> {
        i2c::init(dcxo)?;

        write(dcxo, 255, 0x00)?;  // PAGE
        write_no_ack_value(dcxo, 7, 0x80)?;  // RESET
        clock::spin_us(100_000);  // required? not specified in datasheet.

        write(dcxo, 255, 0x00)?;  // PAGE
        write(dcxo, 69,  0x00)?;  // Disable FCAL override.
                                  // Note: Value 0x00 from Table 5.6 is inconsistent with Table 5.7,
                                  // which shows bit 0 as reserved and =1.
        write(dcxo, 17,  0x00)?;  // Synchronously disable output

        // The Si549 has no ID register, so we check that it responds correctly
        // by writing values to a RAM-like register and reading them back.
        for test_value in 0..255 {
            write(dcxo, 23, test_value)?;
            let readback = read(dcxo, 23)?;
            if readback != test_value {
                return Err("Si549 detection failed");
            }
        }

        write(dcxo, 23,  hsdiv as u8)?;
        write(dcxo, 24,  (hsdiv >> 8) as u8 | (lsdiv << 4))?;
        write(dcxo, 26,  fbdiv as u8)?;
        write(dcxo, 27,  (fbdiv >> 8) as u8)?;
        write(dcxo, 28,  (fbdiv >> 16) as u8)?;
        write(dcxo, 29,  (fbdiv >> 24) as u8)?;
        write(dcxo, 30,  (fbdiv >> 32) as u8)?;
        write(dcxo, 31,  (fbdiv >> 40) as u8)?;

        write(dcxo, 7,   0x08)?;  // Start FCAL
        write(dcxo, 17,  0x01)?;  // Synchronously enable output

        Ok(())
    }

    pub fn set_adpll(dcxo: i2c::Dcxo, adpll: i32) -> Result<(), &'static str> {
        write(dcxo, 231, adpll as u8)?;
        write(dcxo, 232, (adpll >> 8) as u8)?;
        write(dcxo, 233, (adpll >> 16) as u8)?;
        clock::spin_us(100);
        Ok(())
    }

    pub fn get_adpll(dcxo: i2c::Dcxo) -> Result<i32, &'static str> {
        let b1 = read(dcxo, 231)? as i32;
        let b2 = read(dcxo, 232)? as i32;
        let b3 = read(dcxo, 233)? as i8 as i32;
        Ok(b3 << 16 | b2 << 8 | b1)
    }
}

fn get_frequencies() -> (u32, u32, u32) {
    unsafe {
        csr::wrpll::frequency_counter_update_en_write(1);
        // wait for at least one full update cycle (> 2 timer periods)
        clock::spin_us(200_000);
        csr::wrpll::frequency_counter_update_en_write(0);
        let helper = csr::wrpll::frequency_counter_counter_helper_read();
        let main = csr::wrpll::frequency_counter_counter_rtio_read();
        let cdr = csr::wrpll::frequency_counter_counter_rtio_rx0_read();
        (helper, main, cdr)
    }
}

fn log_frequencies() -> (u32, u32, u32) {
    let (f_helper, f_main, f_cdr) = get_frequencies();
    let conv_khz = |f| 4*(f as u64)*(csr::CONFIG_CLOCK_FREQUENCY as u64)/(1000*(1 << 23));
    info!("helper clock frequency: {}kHz ({})", conv_khz(f_helper), f_helper);
    info!("main clock frequency: {}kHz ({})", conv_khz(f_main), f_main);
    info!("CDR clock frequency: {}kHz ({})", conv_khz(f_cdr), f_cdr);
    (f_helper, f_main, f_cdr)
}

fn get_ddmtd_main_tag() -> u16 {
    unsafe {
        csr::wrpll::ddmtd_main_arm_write(1);
        while csr::wrpll::ddmtd_main_arm_read() != 0 {}
        csr::wrpll::ddmtd_main_tag_read()
    }
}

fn get_ddmtd_helper_tag() -> u16 {
    unsafe {
        csr::wrpll::ddmtd_helper_arm_write(1);
        while csr::wrpll::ddmtd_helper_arm_read() != 0 {}
        csr::wrpll::ddmtd_helper_tag_read()
    }
}

pub fn init() {
    info!("initializing...");

    unsafe { csr::wrpll::helper_reset_write(1); }

    unsafe {
        csr::wrpll::helper_dcxo_i2c_address_write(si549::ADDRESS);
        csr::wrpll::main_dcxo_i2c_address_write(si549::ADDRESS);
    }

    #[cfg(rtio_frequency = "125.0")]
    let (h_hsdiv, h_lsdiv, h_fbdiv) = (0x05c, 0, 0x04b5badb98a);
    #[cfg(rtio_frequency = "125.0")]
    let (m_hsdiv, m_lsdiv, m_fbdiv) = (0x05c, 0, 0x04b5c447213);

    si549::program(i2c::Dcxo::Main, m_hsdiv, m_lsdiv, m_fbdiv)
        .expect("cannot initialize main Si549");
    si549::program(i2c::Dcxo::Helper, h_hsdiv, h_lsdiv, h_fbdiv)
        .expect("cannot initialize helper Si549");
    // Si549 Settling Time for Large Frequency Change.
    // Datasheet said 10ms but it lied.
    clock::spin_us(50_000);

    unsafe { csr::wrpll::helper_reset_write(0); }
    clock::spin_us(1);
}

pub fn diagnostics() {
    log_frequencies();

    info!("ADPLL test:");
    // +/-10ppm
    si549::set_adpll(i2c::Dcxo::Helper, -85911).expect("ADPLL write failed");
    si549::set_adpll(i2c::Dcxo::Main, 85911).expect("ADPLL write failed");
    log_frequencies();
    si549::set_adpll(i2c::Dcxo::Helper, 0).expect("ADPLL write failed");
    si549::set_adpll(i2c::Dcxo::Main, 0).expect("ADPLL write failed");

    let mut tags = [0; 10];
    for i in 0..tags.len() {
        tags[i] = get_ddmtd_main_tag();
    }
    info!("DDMTD main tags: {:?}", tags);
}

fn trim_dcxos(f_helper: u32, f_main: u32, f_cdr: u32) -> Result<(i32, i32), &'static str> {
    const DCXO_STEP: i64 = (1.0e6/0.0001164) as i64;
    const ADPLL_MAX: i64 = (950.0/0.0001164) as i64;

    const TIMER_WIDTH: u32 = 23;
    const COUNTER_DIV: u32 = 2;

    const F_SYS: f64 = csr::CONFIG_CLOCK_FREQUENCY as f64;
    #[cfg(rtio_frequency = "125.0")]
    const F_MAIN: f64 = 125.0e6;
    const F_HELPER: f64 = F_MAIN * ((1 << 15) as f64)/((1<<15) as f64 + 1.0);

    const SYS_COUNTS: i64 = (1 << (TIMER_WIDTH - COUNTER_DIV)) as i64;
    const EXP_MAIN_COUNTS: i64 = ((SYS_COUNTS as f64) * (F_MAIN/F_SYS)) as i64;
    const EXP_HELPER_COUNTS: i64 = ((SYS_COUNTS as f64) * (F_HELPER/F_SYS)) as i64;

    info!("after {} sys counts", SYS_COUNTS);
    info!("expect {} main/CDR counts", EXP_MAIN_COUNTS);
    info!("expect {} helper counts", EXP_HELPER_COUNTS);

    // calibrate the SYS clock to the CDR clock and correct the measured counts
    // assume frequency errors are small so we can make an additive correction
    // positive error means sys clock is too fast
    let sys_err: i64 = EXP_MAIN_COUNTS - (f_cdr as i64);
    let main_err: i64 = EXP_MAIN_COUNTS - (f_main as i64) - sys_err;
    let helper_err: i64 = EXP_HELPER_COUNTS - (f_helper as i64) - sys_err;

    info!("sys count err {}", sys_err);
    info!("main counts err {}", main_err);
    info!("helper counts err {}", helper_err);

    // calculate required adjustment to the ADPLL register see
    // https://www.silabs.com/documents/public/data-sheets/si549-datasheet.pdf
    // section 5.6
    let helper_adpll: i64 = helper_err*DCXO_STEP/EXP_HELPER_COUNTS;
    let main_adpll: i64 = main_err*DCXO_STEP/EXP_MAIN_COUNTS;
    if helper_adpll.abs() > ADPLL_MAX {
        return Err("helper DCXO offset too large");
    }
    if main_adpll.abs() > ADPLL_MAX {
        return Err("main DCXO offset too large");
    }

    info!("ADPLL offsets: helper={} main={}", helper_adpll, main_adpll);
    Ok((helper_adpll as i32, main_adpll as i32))
}

fn select_recovered_clock_int(rc: bool) -> Result<(), &'static str> {
    let (f_helper, f_main, f_cdr) = log_frequencies();
    if rc {
        let (helper_adpll, main_adpll) = trim_dcxos(f_helper, f_main, f_cdr)?;
        si549::set_adpll(i2c::Dcxo::Helper, helper_adpll).expect("ADPLL write failed");
        si549::set_adpll(i2c::Dcxo::Main, main_adpll).expect("ADPLL write failed");

        unsafe {
            csr::wrpll::adpll_offset_helper_write(helper_adpll as u32);
            csr::wrpll::adpll_offset_main_write(main_adpll as u32);
            csr::wrpll::helper_dcxo_gpio_enable_write(0);
            csr::wrpll::main_dcxo_gpio_enable_write(0);
            csr::wrpll::helper_dcxo_errors_write(0xff);
            csr::wrpll::main_dcxo_errors_write(0xff);
            csr::wrpll::filter_reset_write(0);
        }

        clock::spin_us(100_000);

        let mut tags = [0; 10];
        for i in 0..tags.len() {
            tags[i] = get_ddmtd_helper_tag();
        }
        info!("DDMTD helper tags: {:?}", tags);

        unsafe {
            csr::wrpll::filter_reset_write(1);
        }
        clock::spin_us(50_000);
        unsafe {
            csr::wrpll::helper_dcxo_gpio_enable_write(1);
            csr::wrpll::main_dcxo_gpio_enable_write(1);
        }
        unsafe {
            info!("error {} {}",
                csr::wrpll::helper_dcxo_errors_read(),
                csr::wrpll::main_dcxo_errors_read());
        }
        info!("new ADPLL: {} {}",
            si549::get_adpll(i2c::Dcxo::Helper)?,
            si549::get_adpll(i2c::Dcxo::Main)?);
    } else {
        si549::set_adpll(i2c::Dcxo::Helper, 0).expect("ADPLL write failed");
        si549::set_adpll(i2c::Dcxo::Main, 0).expect("ADPLL write failed");
    }
    Ok(())
}

pub fn select_recovered_clock(rc: bool) {
    if rc {
        info!("switching to recovered clock");
    } else {
        info!("switching to local XO clock");
    }
    match select_recovered_clock_int(rc) {
        Ok(()) => info!("clock transition completed"),
        Err(e) => error!("clock transition failed: {}", e)
    }
}
