#![feature(asm, lang_items, never_type)]
#![no_std]

extern crate failure;
#[cfg(has_drtio)]
#[macro_use]
extern crate failure_derive;
#[macro_use]
extern crate bitflags;
extern crate byteorder;
extern crate crc;
#[macro_use]
extern crate log;
extern crate io;
extern crate board_misoc;
extern crate proto_artiq;

pub mod pcr;

pub mod i2c;
pub mod spi;

#[cfg(has_kernel_cpu)]
pub mod mailbox;
#[cfg(has_kernel_cpu)]
pub mod rpc_queue;

#[cfg(has_si5324)]
pub mod si5324;

#[cfg(has_slave_fpga_cfg)]
pub mod slave_fpga;
#[cfg(has_serwb_phy_amc)]
pub mod serwb;
#[cfg(has_hmc830_7043)]
pub mod hmc830_7043;
#[cfg(has_ad9154)]
mod ad9154_reg;
#[cfg(has_ad9154)]
pub mod ad9154;
#[cfg(has_allaki_atts)]
pub mod hmc542;
#[cfg(has_grabber)]
pub mod grabber;

#[cfg(has_drtio)]
pub mod drtioaux;
