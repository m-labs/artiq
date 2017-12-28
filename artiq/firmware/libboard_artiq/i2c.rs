#[cfg(has_i2c)]
use csr;

#[cfg(has_i2c)]
mod io {
    use csr;
    use clock;

    pub fn half_period() { clock::spin_us(100) }
    fn sda_bit(busno: u8) -> u8 { 1 << (2 * busno + 1) }
    fn scl_bit(busno: u8) -> u8 { 1 << (2 * busno) }

    pub fn sda_i(busno: u8) -> bool {
        unsafe {
            csr::i2c::in_read() & sda_bit(busno) != 0
        }
    }

    pub fn sda_oe(busno: u8, oe: bool) {
        unsafe {
            let reg = csr::i2c::oe_read();
            let reg = if oe { reg | sda_bit(busno) } else { reg & !sda_bit(busno) };
            csr::i2c::oe_write(reg)
        }
    }

    pub fn sda_o(busno: u8, o: bool) {
        unsafe {
            let reg = csr::i2c::out_read();
            let reg = if o  { reg | sda_bit(busno) } else { reg & !sda_bit(busno) };
            csr::i2c::out_write(reg)
        }
    }

    pub fn scl_oe(busno: u8, oe: bool) {
        unsafe {
            let reg = csr::i2c::oe_read();
            let reg = if oe { reg | scl_bit(busno) } else { reg & !scl_bit(busno) };
            csr::i2c::oe_write(reg)
        }
    }

    pub fn scl_o(busno: u8, o: bool) {
        unsafe {
            let reg = csr::i2c::out_read();
            let reg = if o  { reg | scl_bit(busno) } else { reg & !scl_bit(busno) };
            csr::i2c::out_write(reg)
        }
    }
}

#[cfg(has_i2c)]
pub fn init() {
    for busno in 0..csr::CONFIG_I2C_BUS_COUNT {
        let busno = busno as u8;
        // Set SCL as output, and high level
        io::scl_o(busno, true);
        io::scl_oe(busno, true);
        // Prepare a zero level on SDA so that sda_oe pulls it down
        io::sda_o(busno, false);
        // Release SDA
        io::sda_oe(busno, false);

        // Check the I2C bus is ready
        io::half_period();
        io::half_period();
        if !io::sda_i(busno) {
            error!("SDA is stuck low on bus #{}", busno)
        }
    }
}

#[cfg(has_i2c)]
pub fn start(busno: u8) -> Result<(), ()> {
    if busno as u32 >= csr::CONFIG_I2C_BUS_COUNT {
        return Err(())
    }
    // Set SCL high then SDA low
    io::scl_o(busno, true);
    io::half_period();
    io::sda_oe(busno, true);
    io::half_period();
    Ok(())
}

#[cfg(has_i2c)]
pub fn restart(busno: u8) -> Result<(), ()> {
    if busno as u32 >= csr::CONFIG_I2C_BUS_COUNT {
        return Err(())
    }
    // Set SCL low then SDA high */
    io::scl_o(busno, false);
    io::half_period();
    io::sda_oe(busno, false);
    io::half_period();
    // Do a regular start
    start(busno)?;
    Ok(())
}

#[cfg(has_i2c)]
pub fn stop(busno: u8) -> Result<(), ()> {
    if busno as u32 >= csr::CONFIG_I2C_BUS_COUNT {
        return Err(())
    }
    // First, make sure SCL is low, so that the target releases the SDA line
    io::scl_o(busno, false);
    io::half_period();
    // Set SCL high then SDA high
    io::sda_oe(busno, true);
    io::scl_o(busno, true);
    io::half_period();
    io::sda_oe(busno, false);
    io::half_period();
    Ok(())
}

#[cfg(has_i2c)]
pub fn write(busno: u8, data: u8) -> Result<bool, ()> {
    if busno as u32 >= csr::CONFIG_I2C_BUS_COUNT {
        return Err(())
    }
    // MSB first
    for bit in (0..8).rev() {
        // Set SCL low and set our bit on SDA
        io::scl_o(busno, false);
        io::sda_oe(busno, data & (1 << bit) == 0);
        io::half_period();
        // Set SCL high ; data is shifted on the rising edge of SCL
        io::scl_o(busno, true);
        io::half_period();
    }
    // Check ack
    // Set SCL low, then release SDA so that the I2C target can respond
    io::scl_o(busno, false);
    io::half_period();
    io::sda_oe(busno, false);
    // Set SCL high and check for ack
    io::scl_o(busno, true);
    io::half_period();
    // returns true if acked (I2C target pulled SDA low)
    Ok(!io::sda_i(busno))
}

#[cfg(has_i2c)]
pub fn read(busno: u8, ack: bool) -> Result<u8, ()> {
    if busno as u32 >= csr::CONFIG_I2C_BUS_COUNT {
        return Err(())
    }
    // Set SCL low first, otherwise setting SDA as input may cause a transition
    // on SDA with SCL high which will be interpreted as START/STOP condition.
    io::scl_o(busno, false);
    io::half_period(); // make sure SCL has settled low
    io::sda_oe(busno, false);

    let mut data: u8 = 0;

    // MSB first
    for bit in (0..8).rev() {
        io::scl_o(busno, false);
        io::half_period();
        // Set SCL high and shift data
        io::scl_o(busno, true);
        io::half_period();
        if io::sda_i(busno) { data |= 1 << bit }
    }
    // Send ack
    // Set SCL low and pull SDA low when acking
    io::scl_o(busno, false);
    if ack { io::sda_oe(busno, true) }
    io::half_period();
    // then set SCL high
    io::scl_o(busno, true);
    io::half_period();

    Ok(data)
}

#[cfg(not(has_i2c))]
pub fn init() {}
#[cfg(not(has_i2c))]
pub fn start(_busno: u8) -> Result<(), ()> { Err(()) }
#[cfg(not(has_i2c))]
pub fn restart(_busno: u8) -> Result<(), ()> { Err(()) }
#[cfg(not(has_i2c))]
pub fn stop(_busno: u8) -> Result<(), ()> { Err(()) }
#[cfg(not(has_i2c))]
pub fn write(_busno: u8, _data: u8) -> Result<bool, ()> { Err(()) }
#[cfg(not(has_i2c))]
pub fn read(_busno: u8, _ack: bool) -> Result<u8, ()> { Err(()) }
