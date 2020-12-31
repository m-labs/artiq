use core::i64;
use csr;

const INIT: u64 = i64::MAX as u64;
const FREQ: u64 = csr::CONFIG_CLOCK_FREQUENCY as u64;

pub fn init() {
    unsafe {
        csr::timer0::en_write(0);
        csr::timer0::load_write(INIT);
        csr::timer0::reload_write(INIT);
        csr::timer0::en_write(1);
    }
}

pub fn get_us() -> u64 {
    unsafe {
        csr::timer0::update_value_write(1);
        (INIT - csr::timer0::value_read()) / (FREQ / 1_000_000)
    }
}

pub fn get_ms() -> u64 {
    unsafe {
        csr::timer0::update_value_write(1);
        (INIT - csr::timer0::value_read()) / (FREQ / 1_000)
    }
}

pub fn spin_us(interval: u64) {
    unsafe {
        csr::timer0::update_value_write(1);
        let threshold = csr::timer0::value_read() - interval * (FREQ / 1_000_000);
        while csr::timer0::value_read() > threshold {
            csr::timer0::update_value_write(1)
        }
    }
}
