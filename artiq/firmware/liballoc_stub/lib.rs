#![feature(alloc, allocator_api)]
#![no_std]

extern crate alloc;

use core::alloc::{Layout, GlobalAlloc};

pub struct StubAlloc;

unsafe impl GlobalAlloc for StubAlloc {
    unsafe fn alloc(&self, _layout: Layout) -> *mut u8 {
        unimplemented!()
    }

    unsafe fn dealloc(&self, _ptr: *mut u8, _layout: Layout) {
        unimplemented!()
    }
}
