#![feature(asm, lang_items, never_type)]
#![no_std]

#[macro_use]
extern crate bitflags;
extern crate byteorder;
extern crate crc;
#[macro_use]
extern crate log;
extern crate board;
extern crate io;
extern crate proto;

pub mod pcr;

pub mod i2c;
pub mod spi;

#[cfg(has_si5324)]
pub mod si5324;

#[cfg(has_slave_fpga)]
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

#[cfg(has_drtio)]
pub mod drtioaux;
