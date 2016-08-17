#![no_std]

#[macro_use]
extern crate std_artiq as std;

use std::prelude::v1::*;

#[no_mangle]
pub extern "C" fn rust_main() {
    println!("hello from rust!");
}
