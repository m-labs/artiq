#![feature(alloc, allocator_api)]
#![no_std]

extern crate alloc;

use alloc::allocator::{Layout, AllocErr, Alloc};

pub struct StubAlloc;

unsafe impl<'a> Alloc for &'a StubAlloc {
    unsafe fn alloc(&mut self, _layout: Layout) -> Result<*mut u8, AllocErr> {
        unimplemented!()
    }

    unsafe fn dealloc(&mut self, _ptr: *mut u8, _layout: Layout) {
        unimplemented!()
    }
}
