#![no_std]

#[macro_use]
extern crate std_artiq as std;

use std::prelude::v1::*;
use std::time::Duration;
use scheduler::Scheduler;

pub mod scheduler;

#[no_mangle]
pub extern "C" fn rust_main() {
    // let mut scheduler = Scheduler::new();
    // unsafe {
    //     scheduler.spawn(4096, move |mut io| {
    //         loop {
    //             println!("thread A");
    //             io.sleep(Duration::from_secs(1)).unwrap()
    //         }
    //     });
    //     scheduler.spawn(4096, move |mut io| {
    //         loop {
    //             println!("thread B");
    //             io.sleep(Duration::from_millis(333)).unwrap()
    //         }
    //     });
    // }
    // loop { scheduler.run() }
}
