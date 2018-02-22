#![feature(asm, lang_items)]
#![no_std]

extern crate byteorder;
#[macro_use]
extern crate log;

use core::{cmp, str};

include!(concat!(env!("BUILDINC_DIRECTORY"), "/generated/mem.rs"));
include!(concat!(env!("BUILDINC_DIRECTORY"), "/generated/csr.rs"));
pub mod spr;
pub mod irq;
pub mod cache;
pub mod clock;
pub mod uart;
#[cfg(feature = "uart_console")]
pub mod uart_console;

#[cfg(has_spiflash)]
pub mod spiflash;
pub mod config;

pub mod i2c;
pub mod spi;

#[cfg(has_si5324)]
pub mod si5324;

#[cfg(has_ad9516)]
#[allow(dead_code)]
mod ad9516_reg;
#[cfg(has_ad9516)]
pub mod ad9516;
#[cfg(has_ad9154)]
#[allow(dead_code)]
mod ad9154_reg;
#[cfg(has_ad9154)]
pub mod ad9154;

pub mod boot;

#[cfg(feature = "uart_console")]
pub use uart_console::Console;

pub fn ident(buf: &mut [u8]) -> &str {
    unsafe {
        csr::identifier::address_write(0);
        let len = csr::identifier::data_read();
        let len = cmp::min(len, buf.len() as u8);
        for i in 0..len {
            csr::identifier::address_write(1 + i);
            buf[i as usize] = csr::identifier::data_read();
        }
        str::from_utf8_unchecked(&buf[..len as usize])
    }
}
