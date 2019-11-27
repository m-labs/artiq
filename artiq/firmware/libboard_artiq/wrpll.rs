mod i2c {
    use board_misoc::{csr, clock};

    #[derive(Debug, Clone, Copy)]
    pub enum Dcxo {
        Main,
        Helper
    }

    fn half_period() { clock::spin_us(100) }
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

    pub fn restart(dcxo: Dcxo) {
        // Set SCL low then SDA high */
        scl_o(dcxo, false);
        half_period();
        sda_oe(dcxo, false);
        half_period();
        // Do a regular start
        start(dcxo);
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

pub fn init() {
    info!("initializing...");
    i2c::init(i2c::Dcxo::Main);
    i2c::init(i2c::Dcxo::Helper);
}

pub fn select_recovered_clock(rc: bool) {
    info!("select_recovered_clock: {}", rc);
}
