#![no_std]
#![feature(libc)]

#[macro_use]
extern crate std_artiq as std;
extern crate libc;
#[macro_use]
extern crate log;
extern crate log_buffer;
extern crate byteorder;

use logger::BufferLogger;

mod board;
mod sched;
mod config;
mod clock;
mod rtio_crg;
mod mailbox;

mod logger;
mod cache;

mod kernel_proto;
mod session_proto;

mod kernel;
mod session;

extern {
    fn network_init();
    fn lwip_service();
}

include!(concat!(env!("OUT_DIR"), "/git_info.rs"));

#[no_mangle]
pub unsafe extern fn rust_main() {
    static mut log_buffer: [u8; 4096] = [0; 4096];
    BufferLogger::new(&mut log_buffer[..])
                 .register(move |logger| {
        info!("booting ARTIQ runtime ({})", GIT_COMMIT);

        clock::init();
        rtio_crg::init();
        network_init();

        let mut scheduler = sched::Scheduler::new();
        scheduler.spawn(8192, move |waiter| {
            session::handler(waiter, logger)
        });

        loop {
            lwip_service();
            scheduler.run()
        }
    })
}
