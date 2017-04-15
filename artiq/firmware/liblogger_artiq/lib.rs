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

    pub fn with_instance<R, F: FnOnce(&BufferLogger) -> R>(f: F) -> R {
        f(unsafe { mem::transmute::<*const BufferLogger, &BufferLogger>(LOGGER) })
    }

    pub fn clear(&self) {
        self.buffer.borrow_mut().clear()
    }

    pub fn extract<R, F: FnOnce(&str) -> R>(&self, f: F) -> R {
        f(self.buffer.borrow_mut().extract())
    }

    pub fn set_max_log_level(&self, max_level: LogLevelFilter) {
        self.filter
            .borrow()
            .as_ref()
            .expect("register the logger before setting maximum log level")
            .set(max_level)
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
            let force_uart = match self.buffer.try_borrow_mut() {
                Ok(mut buffer) => {
                    writeln!(buffer, "[{:12}us] {:>5}({}): {}",
                             clock::get_us(), record.level(),
                             record.target(), record.args()).unwrap();
                    false
                }
                Err(_) => {
                    // we're trying to log something while sending the log somewhere,
                    // probably over the network. just let it go to UART.
                    true
                }
            };

            if record.level() <= self.uart_filter.get() || force_uart {
                writeln!(Console, "[{:12}us] {:>5}({}): {}",
                         clock::get_us(), record.level(),
                         record.target(), record.args()).unwrap();
            }
        }
    }
}
