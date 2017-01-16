#![feature(asm)]
#![no_std]

#[macro_use]
extern crate log;

use core::{cmp, ptr, str};

include!(concat!(env!("BUILDINC_DIRECTORY"), "/generated/mem.rs"));
include!(concat!(env!("BUILDINC_DIRECTORY"), "/generated/csr.rs"));
pub mod spr;
pub mod irq;
pub mod clock;
pub mod uart;

#[cfg(has_i2c)]
pub mod i2c;
#[cfg(has_i2c)]
pub mod si5324;

#[cfg(has_ad9516)]
#[allow(dead_code)]
mod ad9516_reg;
#[cfg(has_ad9516)]
pub mod ad9516;
#[cfg(has_converter_spi)]
#[allow(dead_code)]
mod ad9154_reg;
#[cfg(has_converter_spi)]
pub mod ad9154;

extern {
    pub fn flush_cpu_dcache();
    pub fn flush_l2_cache();
}

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
