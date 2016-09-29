#![no_std]
#![feature(libc)]

#[macro_use]
extern crate std_artiq as std;
extern crate libc;
#[macro_use]
extern crate log;
extern crate log_buffer;
extern crate byteorder;

use std::prelude::v1::*;
use buffer_logger::BufferLogger;

pub mod board;
pub mod io;
pub mod config;
pub mod buffer_logger;
pub mod session;

extern {
    fn network_init();
    fn lwip_service();
}

#[no_mangle]
pub unsafe extern fn rust_main() {
    static mut log_buffer: [u8; 4096] = [0; 4096];
    BufferLogger::new(&mut log_buffer[..])
                 .register(move |logger| {
        info!("Accepting network sessions in Rust.");
        network_init();

        let mut scheduler = io::Scheduler::new();
        scheduler.spawn(4096, move |waiter| {
            session::handler(waiter, logger)
        });
        loop {
            lwip_service();
            scheduler.run()
        }
    })
}
