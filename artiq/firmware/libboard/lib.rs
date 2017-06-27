#![feature(asm, lang_items)]
#![no_std]

#[macro_use]
extern crate log;

use core::{cmp, ptr, str};

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
        let len = ptr::read_volatile(csr::IDENTIFIER_MEM_BASE);
        let len = cmp::min(len as usize, buf.len());
        for i in 0..len {
            buf[i] = ptr::read_volatile(csr::IDENTIFIER_MEM_BASE.offset(1 + i as isize)) as u8
        }
        str::from_utf8_unchecked(&buf[..len])
    }
}
