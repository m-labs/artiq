use board_misoc::clock;

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
                watchdog.threshold = clock::get_ms() + interval;
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

    pub fn expired(&self) -> Option<usize> {
        self.watchdogs
            .iter()
            .enumerate()
            .filter(|(_, wd)| wd.active && clock::get_ms() > wd.threshold)
            .min_by_key(|(_, wd)| wd.threshold)
            .map_or(None, |(i, _)| Some(i))
    }
}
