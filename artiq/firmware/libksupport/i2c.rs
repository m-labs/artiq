use board::csr;

fn half_period() {
    unsafe {
        csr::timer_kernel::en_write(0);
        csr::timer_kernel::load_write(csr::CONFIG_CLOCK_FREQUENCY/10000);
        csr::timer_kernel::reload_write(0);
        csr::timer_kernel::en_write(1);

        csr::timer_kernel::update_value_write(1);
        while csr::timer_kernel::value_read() != 0 {
            csr::timer_kernel::update_value_write(1)
        }
    }
}

#[cfg(has_i2c)]
mod imp {
    use board::csr;

    fn sda_bit(busno: u32) -> u32 { 1 << (2 * busno + 1) }
    fn scl_bit(busno: u32) -> u32 { 1 << (2 * busno) }

    pub fn sda_i(busno: u32) -> bool {
        unsafe {
            if busno >= csr::CONFIG_I2C_BUS_COUNT {
                true
            } else {
                csr::i2c::in_read() & sda_bit(busno) != 0
            }
        }
    }

    pub fn sda_oe(busno: u32, oe: bool) {
        unsafe {
            let reg = csr::i2c::oe_read();
            let reg = if oe { reg | sda_bit(busno) } else { reg & !sda_bit(busno) };
            csr::i2c::oe_write(reg);
        }
    }

    pub fn sda_o(busno: u32, o: bool) {
        unsafe {
            let reg = csr::i2c::out_read();
            let reg = if o  { reg | sda_bit(busno) } else { reg & !sda_bit(busno) };
            csr::i2c::out_write(reg)
        }
    }

    pub fn scl_oe(busno: u32, oe: bool) {
        unsafe {
            let reg = csr::i2c::oe_read();
            let reg = if oe { reg | scl_bit(busno) } else { reg & !scl_bit(busno) };
            csr::i2c::oe_write(reg)
        }
    }

    pub fn scl_o(busno: u32, o: bool) {
        unsafe {
            let reg = csr::i2c::out_read();
            let reg = if o  { reg | scl_bit(busno) } else { reg & !scl_bit(busno) };
            csr::i2c::out_write(reg)
        }
    }
}

#[cfg(not(has_i2c))]
mod imp {
    pub fn sda_i(busno: u32) -> bool { true }
    pub fn sda_oe(busno: u32, oe: bool) {}
    pub fn sda_o(busno: u32, o: bool) {}
    pub fn scl_oe(busno: u32, oe: bool) {}
    pub fn scl_o(busno: u32, o: bool) {}
}

use self::imp::*;

pub extern fn init(busno: i32) {
    let busno = busno as u32;

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
        artiq_raise!("I2CError", "SDA is stuck low")
    }
}

pub extern fn start(busno: i32) {
    let busno = busno as u32;

    // Set SCL high then SDA low
    scl_o(busno, true);
    half_period();
    sda_oe(busno, true);
    half_period();
}

pub extern fn stop(busno: i32) {
    let busno = busno as u32;

    // First, make sure SCL is low, so that the target releases the SDA line
    scl_o(busno, false);
    half_period();
    // Set SCL high then SDA high
    sda_oe(busno, true);
    scl_o(busno, true);
    half_period();
    sda_oe(busno, false);
    half_period();
}

pub extern fn write(busno: i32, data: i8) -> bool {
    let (busno, data) = (busno as u32, data as u8);

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
    !sda_i(busno)
}

pub extern fn read(busno: i32, ack: bool) -> i8 {
    let busno = busno as u32;

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

    data as i8
}
