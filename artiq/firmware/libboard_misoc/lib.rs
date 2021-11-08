#![no_std]
#![feature(llvm_asm)]

extern crate byteorder;
#[cfg(feature = "log")]
extern crate log;
#[cfg(feature = "smoltcp")]
extern crate smoltcp;

#[cfg(target_arch = "riscv32")]
#[path = "riscv32/mod.rs"]
mod arch;

#[cfg(target_arch = "riscv32")]
extern crate riscv;

pub use arch::*;

include!(concat!(env!("BUILDINC_DIRECTORY"), "/generated/mem.rs"));
include!(concat!(env!("BUILDINC_DIRECTORY"), "/generated/csr.rs"));
#[cfg(has_dfii)]
include!(concat!(env!("BUILDINC_DIRECTORY"), "/generated/sdram_phy.rs"));
#[cfg(has_dfii)]
pub mod sdram;
pub mod ident;
pub mod clock;
#[cfg(has_uart)]
pub mod uart;
#[cfg(has_spiflash)]
pub mod spiflash;
pub mod config;
#[cfg(feature = "uart_console")]
#[macro_use]
pub mod uart_console;
#[cfg(all(feature = "uart_console", feature = "log"))]
#[macro_use]
pub mod uart_logger;
#[cfg(all(has_ethmac, feature = "smoltcp"))]
pub mod ethmac;
pub mod i2c;
#[cfg(soc_platform = "kasli")]
pub mod i2c_eeprom;
#[cfg(all(soc_platform = "kasli", hw_rev = "v2.0"))]
pub mod io_expander;
#[cfg(all(has_ethmac, feature = "smoltcp"))]
pub mod net_settings;
#[cfg(has_slave_fpga_cfg)]
pub mod slave_fpga;
