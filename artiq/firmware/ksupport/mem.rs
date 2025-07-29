use alloc::alloc::{Layout, alloc, dealloc};
use core::mem;

pub unsafe extern "C" fn nac3_malloc(size: usize) -> *mut u8 {
    let ptr = alloc(Layout::from_size_align_unchecked(size + mem::size_of::<usize>(), 8));
    let size_ptr = ptr.cast::<usize>();
    *size_ptr = size;

    ptr.add(mem::size_of::<usize>())
}

pub unsafe extern "C" fn nac3_free(ptr: *mut u8) {
    let size_ptr = ptr.sub(mem::size_of::<usize>()).cast::<usize>();

    dealloc(
        size_ptr.cast::<u8>(),
        Layout::from_size_align_unchecked(*size_ptr + mem::size_of::<usize>(), 8),
    );
}
