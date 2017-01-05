use csr;
use clock;

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

pub fn init() {
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
            error!("SDA is stuck low on bus #{}", busno)
        }
    }
}

pub fn start(busno: u8) {
    // Set SCL high then SDA low
    scl_o(busno, true);
    half_period();
    sda_oe(busno, true);
    half_period();
}

pub fn restart(busno: u8) {
    // Set SCL low then SDA high */
    scl_o(busno, false);
    half_period();
    sda_oe(busno, false);
    half_period();
    // Do a regular start
    start(busno);
}

pub fn stop(busno: u8) {
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

pub fn write(busno: u8, data: u8) -> bool {
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

pub fn read(busno: u8, ack: bool) -> u8 {
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

    data
}
