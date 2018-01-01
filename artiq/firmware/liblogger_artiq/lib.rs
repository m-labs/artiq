#![no_std]

extern crate log;
extern crate log_buffer;
#[macro_use]
extern crate board;

use core::cell::{Cell, RefCell};
use core::fmt::Write;
use log::{Log, LevelFilter};
use log_buffer::LogBuffer;
use board::clock;

pub struct BufferLogger {
    buffer:      RefCell<LogBuffer<&'static mut [u8]>>,
    uart_filter: Cell<LevelFilter>
}

static mut LOGGER: *const BufferLogger = 0 as *const _;

impl BufferLogger {
    pub fn new(buffer: &'static mut [u8]) -> BufferLogger {
        BufferLogger {
            buffer: RefCell::new(LogBuffer::new(buffer)),
            uart_filter: Cell::new(LevelFilter::Info),
        }
    }

    pub fn register<F: FnOnce()>(&self, f: F) {
        unsafe {
            LOGGER = self;
            log::set_logger(&*LOGGER)
                .expect("global logger can only be initialized once");
        }
        log::set_max_level(LevelFilter::Info);
        f();
    }

    pub fn with<R, F: FnOnce(&BufferLogger) -> R>(f: F) -> R {
        f(unsafe { &*LOGGER })
    }

    pub fn clear(&self) {
        self.buffer.borrow_mut().clear()
    }

    pub fn is_empty(&self) -> bool {
        self.buffer.borrow_mut().extract().len() == 0
    }

    pub fn extract<R, F: FnOnce(&str) -> R>(&self, f: F) -> R {
        let old_log_level = log::max_level();
        log::set_max_level(LevelFilter::Off);
        let result = f(self.buffer.borrow_mut().extract());
        log::set_max_level(old_log_level);
        result
    }

    pub fn uart_log_level(&self) -> LevelFilter {
        self.uart_filter.get()
    }

    pub fn set_uart_log_level(&self, max_level: LevelFilter) {
        self.uart_filter.set(max_level)
    }
}

// required for impl Log
unsafe impl Sync for BufferLogger {}

impl Log for BufferLogger {
    fn enabled(&self, _metadata: &log::Metadata) -> bool {
        true
    }

    fn log(&self, record: &log::Record) {
        if self.enabled(record.metadata()) {
            let timestamp = clock::get_us();
            let seconds   = timestamp / 1_000_000;
            let micros    = timestamp % 1_000_000;

            writeln!(self.buffer.borrow_mut(),
                     "[{:6}.{:06}s] {:>5}({}): {}", seconds, micros,
                     record.level(), record.target(), record.args()).unwrap();

            if record.level() <= self.uart_filter.get() {
                println!("[{:6}.{:06}s] {:>5}({}): {}", seconds, micros,
                         record.level(), record.target(), record.args());
            }
        }
    }

    fn flush(&self) {
    }
}
