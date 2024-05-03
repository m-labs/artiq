#![no_std]
#![unstable(feature = "panic_unwind", issue = "32837")]
#![feature(link_cfg)]
#![feature(nll)]
#![feature(staged_api)]
#![feature(static_nobundle)]
#![feature(c_unwind)]
#![cfg_attr(not(target_env = "msvc"), feature(libc))]

mod libunwind;
pub use libunwind::*;
