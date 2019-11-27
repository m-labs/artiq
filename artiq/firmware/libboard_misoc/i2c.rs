#[cfg(has_i2c)]
mod imp {
    use super::super::{csr, clock};

    const INVALID_BUS: &'static str = "Invalid I2C bus";

    fn half_period() { clock::spin_us(100) }
    fn sda_bit(busno: u8) -> u8 { 1 << (2 * busno + 1) }
    fn scl_bit(busno: u8) -> u8 { 1 << (2 * busno) }

    fn sda_i(busno: u8) -> bool {
        unsafe {
            csr::i2c::in_read() & sda_bit(busno) != 0
        }
    }

    fn sda_oe(busno: u8, oe: bool) {
        unsafe {
            let reg = csr::i2c::oe_read();
            let reg = if oe { reg | sda_bit(busno) } else { reg & !sda_bit(busno) };
            csr::i2c::oe_write(reg)
        }
    }

    fn sda_o(busno: u8, o: bool) {
        unsafe {
            let reg = csr::i2c::out_read();
            let reg = if o  { reg | sda_bit(busno) } else { reg & !sda_bit(busno) };
            csr::i2c::out_write(reg)
        }
    }

    fn scl_oe(busno: u8, oe: bool) {
        unsafe {
            let reg = csr::i2c::oe_read();
            let reg = if oe { reg | scl_bit(busno) } else { reg & !scl_bit(busno) };
            csr::i2c::oe_write(reg)
        }
    }

    fn scl_o(busno: u8, o: bool) {
        unsafe {
            let reg = csr::i2c::out_read();
            let reg = if o  { reg | scl_bit(busno) } else { reg & !scl_bit(busno) };
            csr::i2c::out_write(reg)
        }
    }

    pub fn init() -> Result<(), &'static str> {
        for busno in 0..csr::CONFIG_I2C_BUS_COUNT {
            let busno = busno as u8;
            // Set SCL as output, and high level
            scl_o(busno, true);
            scl_oe(busno, true);
            // Prepare a zero level on SDA so that sda_oe pulls it down
            sda_o(busno, false);
            // Release SDA
            sda_oe(busno, false);

            // Check the I2C bus is ready
            half_period();
            half_period();
            if !sda_i(busno) {
                // Try toggling SCL a few times
                for _bit in 0..8 {
                    scl_o(busno, false);
                    half_period();
                    scl_o(busno, true);
                    half_period();
                }
            }

            if !sda_i(busno) {
                return Err("SDA is stuck low and doesn't get unstuck");
            }
        }
        Ok(())
    }

    pub fn start(busno: u8) -> Result<(), &'static str> {
        if busno as u32 >= csr::CONFIG_I2C_BUS_COUNT {
            return Err(INVALID_BUS)
        }
        // Set SCL high then SDA low
        scl_o(busno, true);
        half_period();
        sda_oe(busno, true);
        half_period();
        Ok(())
    }

    pub fn restart(busno: u8) -> Result<(), &'static str> {
        if busno as u32 >= csr::CONFIG_I2C_BUS_COUNT {
            return Err(INVALID_BUS)
        }
        // Set SCL low then SDA high */
        scl_o(busno, false);
        half_period();
        sda_oe(busno, false);
        half_period();
        // Do a regular start
        start(busno)?;
        Ok(())
    }

    pub fn stop(busno: u8) -> Result<(), &'static str> {
        if busno as u32 >= csr::CONFIG_I2C_BUS_COUNT {
            return Err(INVALID_BUS)
        }
        // First, make sure SCL is low, so that the target releases the SDA line
        scl_o(busno, false);
        half_period();
        // Set SCL high then SDA high
        sda_oe(busno, true);
        scl_o(busno, true);
        half_period();
        sda_oe(busno, false);
        half_period();
        Ok(())
    }

    pub fn write(busno: u8, data: u8) -> Result<bool, &'static str> {
        if busno as u32 >= csr::CONFIG_I2C_BUS_COUNT {
            return Err(INVALID_BUS)
        }
        // MSB first
        for bit in (0..8).rev() {
            // Set SCL low and set our bit on SDA
            scl_o(busno, false);
            sda_oe(busno, data & (1 << bit) == 0);
            half_period();
            // Set SCL high ; data is shifted on the rising edge of SCL
            scl_o(busno, true);
            half_period();
        }
        // Check ack
        // Set SCL low, then release SDA so that the I2C target can respond
        scl_o(busno, false);
        half_period();
        sda_oe(busno, false);
        // Set SCL high and check for ack
        scl_o(busno, true);
        half_period();
        // returns true if acked (I2C target pulled SDA low)
        Ok(!sda_i(busno))
    }

    pub fn read(busno: u8, ack: bool) -> Result<u8, &'static str> {
        if busno as u32 >= csr::CONFIG_I2C_BUS_COUNT {
            return Err(INVALID_BUS)
        }
        // Set SCL low first, otherwise setting SDA as input may cause a transition
        // on SDA with SCL high which will be interpreted as START/STOP condition.
        scl_o(busno, false);
        half_period(); // make sure SCL has settled low
        sda_oe(busno, false);

        let mut data: u8 = 0;

        // MSB first
        for bit in (0..8).rev() {
            scl_o(busno, false);
            half_period();
            // Set SCL high and shift data
            scl_o(busno, true);
            half_period();
            if sda_i(busno) { data |= 1 << bit }
        }
        // Send ack
        // Set SCL low and pull SDA low when acking
        scl_o(busno, false);
        if ack { sda_oe(busno, true) }
        half_period();
        // then set SCL high
        scl_o(busno, true);
        half_period();

        Ok(data)
    }

    pub fn pca9548_select(busno: u8, address: u8, channels: u8) -> Result<(), &'static str> {
        start(busno)?;
        if !write(busno, address << 1)? {
            return Err("PCA9548 failed to ack write address")
        }
        if !write(busno, channels)? {
            return Err("PCA9548 failed to ack control word")
        }
        stop(busno)?;
        Ok(())
    }
}

#[cfg(not(has_i2c))]
mod imp {
    const NO_I2C: &'static str = "No I2C support on this platform";
    pub fn init() -> Result<(), &'static str> { Err(NO_I2C) }
    pub fn start(_busno: u8) -> Result<(), &'static str> { Err(NO_I2C) }
    pub fn restart(_busno: u8) -> Result<(), &'static str> { Err(NO_I2C) }
    pub fn stop(_busno: u8) -> Result<(), &'static str> { Err(NO_I2C) }
    pub fn write(_busno: u8, _data: u8) -> Result<bool, &'static str> { Err(NO_I2C) }
    pub fn read(_busno: u8, _ack: bool) -> Result<u8, &'static str> { Err(NO_I2C) }
    pub fn pca9548_select(_busno: u8, _address: u8, _channels: u8) -> Result<(), &'static str> { Err(NO_I2C) }
}

pub use self::imp::*;
