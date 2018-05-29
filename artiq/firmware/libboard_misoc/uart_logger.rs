use core::fmt::Write;
use log::{Log, LevelFilter, Metadata, Record, set_logger, set_max_level};

use clock;
use uart_console::Console;

pub struct ConsoleLogger;

impl ConsoleLogger {
    pub fn register() {
        static LOGGER: ConsoleLogger = ConsoleLogger;
        set_logger(&LOGGER).expect("global logger can only be initialized once");
        set_max_level(LevelFilter::Trace);
    }
}

impl Log for ConsoleLogger {
    fn enabled(&self, _metadata: &Metadata) -> bool {
        true
    }

    fn log(&self, record: &Record) {
        if self.enabled(record.metadata()) {
            let timestamp = clock::get_us();
            let seconds   = timestamp / 1_000_000;
            let micros    = timestamp % 1_000_000;

            let _ = writeln!(Console, "[{:6}.{:06}s] {:>5}({}): {}",
                             seconds, micros, record.level(), record.target(), record.args());
        }
    }

    fn flush(&self) {
    }
}

