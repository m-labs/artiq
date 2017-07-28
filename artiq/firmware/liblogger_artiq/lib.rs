#![no_std]

extern crate log;
extern crate log_buffer;
extern crate board;

use core::{mem, ptr};
use core::cell::{Cell, RefCell};
use core::fmt::Write;
use log::{Log, LogMetadata, LogRecord, LogLevelFilter, MaxLogLevelFilter};
use log_buffer::LogBuffer;
use board::{Console, clock};

pub struct BufferLogger {
    buffer:      RefCell<LogBuffer<&'static mut [u8]>>,
    filter:      RefCell<Option<MaxLogLevelFilter>>,
    uart_filter: Cell<LogLevelFilter>
}

static mut LOGGER: *const BufferLogger = 0 as *const _;

impl BufferLogger {
    pub fn new(buffer: &'static mut [u8]) -> BufferLogger {
        BufferLogger {
            buffer: RefCell::new(LogBuffer::new(buffer)),
            filter: RefCell::new(None),
            uart_filter: Cell::new(LogLevelFilter::Info),
        }
    }

    pub fn register<F: FnOnce()>(&self, f: F) {
        // log::set_logger_raw captures a pointer to ourselves, so we must prevent
        // ourselves from being moved or dropped after that function is called (and
        // before log::shutdown_logger_raw is called).
        unsafe {
            log::set_logger_raw(|max_log_level| {
                max_log_level.set(LogLevelFilter::Info);
                *self.filter.borrow_mut() = Some(max_log_level);
                self as *const Log
            }).expect("global logger can only be initialized once");
            LOGGER = self;
        }
        f();
        log::shutdown_logger_raw().unwrap();
        unsafe {
            LOGGER = ptr::null();
        }
    }

    pub fn with<R, F: FnOnce(&BufferLogger) -> R>(f: F) -> R {
        f(unsafe { mem::transmute::<*const BufferLogger, &BufferLogger>(LOGGER) })
    }

    pub fn clear(&self) {
        self.buffer.borrow_mut().clear()
    }

    pub fn is_empty(&self) -> bool {
        self.buffer.borrow_mut().extract().len() == 0
    }

    pub fn extract<R, F: FnOnce(&str) -> R>(&self, f: F) -> R {
        let old_log_level = self.max_log_level();
        self.set_max_log_level(LogLevelFilter::Off);
        let result = f(self.buffer.borrow_mut().extract());
        self.set_max_log_level(old_log_level);
        result
    }

    pub fn max_log_level(&self) -> LogLevelFilter {
        self.filter
            .borrow()
            .as_ref()
            .expect("register the logger before touching maximum log level")
            .get()
    }

    pub fn set_max_log_level(&self, max_level: LogLevelFilter) {
        self.filter
            .borrow()
            .as_ref()
            .expect("register the logger before touching maximum log level")
            .set(max_level)
    }

    pub fn uart_log_level(&self) -> LogLevelFilter {
        self.uart_filter.get()
    }

    pub fn set_uart_log_level(&self, max_level: LogLevelFilter) {
        self.uart_filter.set(max_level)
    }
}

// required for impl Log
unsafe impl Sync for BufferLogger {}

impl Log for BufferLogger {
    fn enabled(&self, _metadata: &LogMetadata) -> bool {
        true
    }

    fn log(&self, record: &LogRecord) {
        if self.enabled(record.metadata()) {
            let timestamp = clock::get_us();
            let seconds   = timestamp / 1_000_000;
            let micros    = timestamp % 1_000_000;

            writeln!(self.buffer.borrow_mut(),
                     "[{:6}.{:06}s] {:>5}({}): {}", seconds, micros,
                     record.level(), record.target(), record.args()).unwrap();

            if record.level() <= self.uart_filter.get() {
                writeln!(Console,
                         "[{:6}.{:06}s] {:>5}({}): {}", seconds, micros,
                         record.level(), record.target(), record.args()).unwrap();
            }
        }
    }
}
