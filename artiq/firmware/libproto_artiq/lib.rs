#![no_std]
#![cfg_attr(feature = "alloc", feature(alloc))]

extern crate failure;
#[macro_use]
extern crate failure_derive;
#[cfg(feature = "alloc")]
extern crate alloc;
extern crate cslice;
#[cfg(feature = "log")]
#[macro_use]
extern crate log;

extern crate io;
extern crate dyld;

// Internal protocols.
pub mod kernel_proto;
pub mod drtioaux_proto;

// External protocols.
#[cfg(feature = "alloc")]
pub mod mgmt_proto;
#[cfg(feature = "alloc")]
pub mod analyzer_proto;
#[cfg(feature = "alloc")]
pub mod moninj_proto;
#[cfg(feature = "alloc")]
pub mod session_proto;
pub mod rpc_proto;
