use i2c;

pub fn select(busno: u8, address: u8, channels: u8) -> Result<(), &'static str> {
    i2c::start(busno).unwrap();
    if !i2c::write(busno, address << 1).unwrap() {
        return Err("PCA9548 failed to ack write address")
    }
    if !i2c::write(busno, channels).unwrap() {
        return Err("PCA9548 failed to ack control word")
    }
    i2c::stop(busno).unwrap();
    Ok(())
}
