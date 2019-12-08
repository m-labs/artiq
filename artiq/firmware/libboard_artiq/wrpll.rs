use board_misoc::{csr, clock};

mod i2c {
    use board_misoc::{csr, clock};

    #[derive(Debug, Clone, Copy)]
    pub enum Dcxo {
        Main,
        Helper
    }

    fn half_period() { clock::spin_us(10) }
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

    const ADDRESS: u8 = 0x55;

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
        clock::spin_us(50_000);   // required? not specified in datasheet.

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
}

fn get_helper_frequency() -> u32 {
    unsafe { csr::wrpll::helper_frequency_start_write(1); }
    clock::spin_us(10_000);
    unsafe { csr::wrpll::helper_frequency_stop_write(1); }
    clock::spin_us(1);
    unsafe { csr::wrpll::helper_frequency_counter_read() }
}

pub fn init() {
    info!("initializing...");

    unsafe { csr::wrpll::helper_reset_write(1); }

    #[cfg(rtio_frequency = "125.0")]
    let (m_hsdiv, m_lsdiv, m_fbdiv) = (0x017, 2, 0x04b5badb98a);
    #[cfg(rtio_frequency = "125.0")]
    let (h_hsdiv, h_lsdiv, h_fbdiv) = (0x017, 2, 0x04b5c447213);

    si549::program(i2c::Dcxo::Main, m_hsdiv, m_lsdiv, m_fbdiv)
        .expect("cannot initialize main Si549");
    si549::program(i2c::Dcxo::Helper, h_hsdiv, h_lsdiv, h_fbdiv)
        .expect("cannot initialize helper Si549");

    clock::spin_us(10_000); // Settling Time after FS Change
    unsafe { csr::wrpll::helper_reset_write(0); }
    clock::spin_us(1);

    info!("helper clock frequency: {}MHz", get_helper_frequency()/10000);

    info!("DDMTD test:");
    for _ in 0..20 {
        unsafe {
            csr::wrpll::ddmtd_main_arm_write(1);
            while csr::wrpll::ddmtd_main_arm_read() != 0 {}
            info!("{}", csr::wrpll::ddmtd_main_tag_read());
        }
    }
}

pub fn select_recovered_clock(rc: bool) {
    info!("select_recovered_clock: {}", rc);
}
