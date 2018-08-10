#![feature(libc, panic_unwind, unwind_attributes)]
#![crate_name = "artiq_support"]
#![crate_type = "cdylib"]

extern crate std as core;
extern crate libc;
extern crate unwind;

// Note: this does *not* match the cslice crate!
// ARTIQ Python has the slice length field fixed at 32 bits, even on 64-bit platforms.
mod cslice {
    use core::marker::PhantomData;
    use core::convert::AsRef;
    use core::slice;

    #[repr(C)]
    #[derive(Clone, Copy)]
    pub struct CSlice<'a, T> {
        base: *const T,
        len: u32,
        phantom: PhantomData<&'a ()>
    }

    impl<'a, T> CSlice<'a, T> {
        pub fn len(&self) -> usize {
            self.len as usize
        }
    }

    impl<'a, T> AsRef<[T]> for CSlice<'a, T> {
        fn as_ref(&self) -> &[T] {
            unsafe {
                slice::from_raw_parts(self.base, self.len as usize)
            }
        }
    }

    pub trait AsCSlice<'a, T> {
        fn as_c_slice(&'a self) -> CSlice<'a, T>;
    }

    impl<'a> AsCSlice<'a, u8> for str {
        fn as_c_slice(&'a self) -> CSlice<'a, u8> {
            CSlice {
                base: self.as_ptr(),
                len: self.len() as u32,
                phantom: PhantomData
            }
        }
    }
}

#[path = "."]
pub mod eh {
    #[path = "../../firmware/libeh/dwarf.rs"]
    pub mod dwarf;
}
#[path = "../../firmware/ksupport/eh_artiq.rs"]
pub mod eh_artiq;

use std::{str, process};

fn terminate(exception: &eh_artiq::Exception, mut _backtrace: &mut [usize]) -> ! {
    println!("Uncaught {}: {} ({}, {}, {})",
             str::from_utf8(exception.name.as_ref()).unwrap(),
             str::from_utf8(exception.message.as_ref()).unwrap(),
             exception.param[0],
             exception.param[1],
             exception.param[2]);
    println!("at {}:{}:{}",
             str::from_utf8(exception.file.as_ref()).unwrap(),
             exception.line,
             exception.column);
    process::exit(1);
}

#[export_name = "now"]
pub static mut NOW: i64 = 0;

#[export_name = "watchdog_set"]
pub extern fn watchdog_set(ms: i64) -> i32 {
    println!("watchdog_set {}", ms);
    ms as i32
}

#[export_name = "watchdog_clear"]
pub extern fn watchdog_clear(id: i32) {
    println!("watchdog_clear {}", id);
}
