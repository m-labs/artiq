#![no_std]
#![feature(asm)]

extern crate byteorder;

#[cfg(target_arch = "or1k")]
#[path = "or1k/mod.rs"]
mod arch;

pub use arch::*;

include!(concat!(env!("BUILDINC_DIRECTORY"), "/generated/mem.rs"));
include!(concat!(env!("BUILDINC_DIRECTORY"), "/generated/csr.rs"));
include!(concat!(env!("BUILDINC_DIRECTORY"), "/generated/sdram_phy.rs"));
pub mod sdram;
pub mod ident;
pub mod clock;
pub mod uart;
#[cfg(has_spiflash)]
pub mod spiflash;
pub mod config;
#[cfg(feature = "uart_console")]
pub mod uart_console;
