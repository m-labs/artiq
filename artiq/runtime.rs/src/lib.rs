#![no_std]

#[macro_use]
extern crate std_artiq as std;
extern crate byteorder;

use std::prelude::v1::*;

pub mod io;
pub mod session;

extern {
    fn network_init();
    fn lwip_service();
}

#[no_mangle]
pub unsafe extern fn rust_main() {
    println!("Accepting network sessions in Rust.");
    network_init();

    let mut scheduler = io::Scheduler::new();
    scheduler.spawn(4096, session::handler);
    loop {
        lwip_service();
        scheduler.run()
    }
}
