#![no_std]
#![feature(libc, borrow_state, const_fn, try_borrow)]

#[macro_use]
extern crate std_artiq as std;
extern crate libc;
#[macro_use]
extern crate log;
extern crate log_buffer;
extern crate byteorder;
extern crate fringe;
extern crate lwip;

use logger::BufferLogger;

mod board;
mod config;
mod clock;
mod rtio_crg;
mod mailbox;

mod urc;
mod sched;
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
    static mut LOG_BUFFER: [u8; 4096] = [0; 4096];
    BufferLogger::new(&mut LOG_BUFFER[..])
                 .register(move || {
        info!("booting ARTIQ runtime ({})", GIT_COMMIT);

        clock::init();
        rtio_crg::init();
        network_init();

        let mut scheduler = sched::Scheduler::new();
        scheduler.spawner().spawn(8192, session::handler);

        loop {
            scheduler.run();
            lwip_service();
        }
    })
}
