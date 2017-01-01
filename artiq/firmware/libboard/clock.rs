use csr;

const INIT: u64 = ::core::i64::MAX as u64;
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

#[derive(Debug, Clone, Copy)]
struct Watchdog {
    active:    bool,
    threshold: u64
}

pub const MAX_WATCHDOGS: usize = 16;

#[derive(Debug)]
pub struct WatchdogSet {
    watchdogs: [Watchdog; MAX_WATCHDOGS]
}

impl WatchdogSet {
    pub fn new() -> WatchdogSet {
        WatchdogSet {
            watchdogs: [Watchdog { active: false, threshold: 0 }; MAX_WATCHDOGS]
        }
    }

    pub fn set_ms(&mut self, interval: u64) -> Result<usize, ()> {
        for (index, watchdog) in self.watchdogs.iter_mut().enumerate() {
            if !watchdog.active {
                watchdog.active = true;
                watchdog.threshold = get_ms() + interval;
                return Ok(index)
            }
        }

        Err(())
    }

    pub fn clear(&mut self, index: usize) {
        if index < MAX_WATCHDOGS {
            self.watchdogs[index].active = false
        }
    }

    pub fn expired(&self) -> bool {
        self.watchdogs.iter()
            .filter(|wd| wd.active)
            .min_by_key(|wd| wd.threshold)
            .map_or(false, |wd| get_ms() > wd.threshold)
    }
}
