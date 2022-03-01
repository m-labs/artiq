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

    fn scl_i(busno: u8) -> bool {
        unsafe {
            csr::i2c::in_read() & scl_bit(busno) != 0
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
            scl_oe(busno, false);
            sda_oe(busno, false);
            scl_o(busno, false);
            sda_o(busno, false);

            // Check the I2C bus is ready
            half_period();
            half_period();
            if !sda_i(busno) {
                // Try toggling SCL a few times
                for _bit in 0..8 {
                    scl_oe(busno, true);
                    half_period();
                    scl_oe(busno, false);
                    half_period();
                }
            }

            if !sda_i(busno) {
                return Err("SDA is stuck low and doesn't get unstuck");
            }
            if !scl_i(busno) {
                return Err("SCL is stuck low and doesn't get unstuck");
            }
            // postcondition: SCL and SDA high
        }
        Ok(())
    }

    pub fn start(busno: u8) -> Result<(), &'static str> {
        if busno as u32 >= csr::CONFIG_I2C_BUS_COUNT {
            return Err(INVALID_BUS)
        }
        // precondition: SCL and SDA high
        if !scl_i(busno) {
            return Err("SCL is stuck low and doesn't get unstuck");
        }
        if !sda_i(busno) {
            return Err("SDA arbitration lost");
        }
        sda_oe(busno, true);
        half_period();
        scl_oe(busno, true);
        // postcondition: SCL and SDA low
        Ok(())
    }

    pub fn restart(busno: u8) -> Result<(), &'static str> {
        if busno as u32 >= csr::CONFIG_I2C_BUS_COUNT {
            return Err(INVALID_BUS)
        }
        // precondition SCL and SDA low
        sda_oe(busno, false);
        half_period();
        scl_oe(busno, false);
        half_period();
        start(busno)?;
        // postcondition: SCL and SDA low
        Ok(())
    }

    pub fn stop(busno: u8) -> Result<(), &'static str> {
        if busno as u32 >= csr::CONFIG_I2C_BUS_COUNT {
            return Err(INVALID_BUS)
        }
        // precondition: SCL and SDA low
        half_period();
        scl_oe(busno, false);
        half_period();
        sda_oe(busno, false);
        half_period();
        if !sda_i(busno) {
            return Err("SDA arbitration lost");
        }
        // postcondition: SCL and SDA high
        Ok(())
    }

    pub fn write(busno: u8, data: u8) -> Result<bool, &'static str> {
        if busno as u32 >= csr::CONFIG_I2C_BUS_COUNT {
            return Err(INVALID_BUS)
        }
        // precondition: SCL and SDA low
        // MSB first
        for bit in (0..8).rev() {
            sda_oe(busno, data & (1 << bit) == 0);
            half_period();
            scl_oe(busno, false);
            half_period();
            scl_oe(busno, true);
        }
        sda_oe(busno, false);
        half_period();
        scl_oe(busno, false);
        half_period();
        // Read ack/nack
        let ack = !sda_i(busno);
        scl_oe(busno, true);
        sda_oe(busno, true);
        // postcondition: SCL and SDA low

        Ok(ack)
    }

    pub fn read(busno: u8, ack: bool) -> Result<u8, &'static str> {
        if busno as u32 >= csr::CONFIG_I2C_BUS_COUNT {
            return Err(INVALID_BUS)
        }
        // precondition: SCL and SDA low
        sda_oe(busno, false);

        let mut data: u8 = 0;

        // MSB first
        for bit in (0..8).rev() {
            half_period();
            scl_oe(busno, false);
            half_period();
            if sda_i(busno) { data |= 1 << bit }
            scl_oe(busno, true);
        }
        // Send ack/nack
        sda_oe(busno, ack);
        half_period();
        scl_oe(busno, false);
        half_period();
        scl_oe(busno, true);
        sda_oe(busno, true);
        // postcondition: SCL and SDA low

        Ok(data)
    }

    pub fn switch_select(busno: u8, address: u8, mask: u8) -> Result<(), &'static str> {
        // address in 7-bit form
        // mask in format of 1 << channel (or 0 for disabling output)
        // PCA9548 support only for now
        start(busno)?;
        if !write(busno, address << 1)? {
            return Err("PCA9548 failed to ack write address")
        }
        if !write(busno, mask)? {
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
    pub fn switch_select(_busno: u8, _address: u8, _mask: u8) -> Result<(), &'static str> { Err(NO_I2C) }
}

pub use self::imp::*;
