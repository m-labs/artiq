use alloc::alloc::{Layout, alloc, dealloc};
use core::mem;

pub unsafe extern "C" fn nac3_malloc(size: usize) -> *mut u8 {
    let ptr = alloc(
        Layout::from_size_align_unchecked(size + 2 * mem::size_of::<usize>(), 8)
    );
    let size_ptr = ptr.cast::<usize>();
    *size_ptr = size;

    let rc_ptr = size_ptr.add(1);
    *rc_ptr = 0;

    rc_ptr.add(1).cast()
}

pub unsafe extern "C" fn nac3_rc_incr(ptr: *mut u8) {
    let ptr = ptr.cast::<usize>().sub(1);
    *ptr += 1;
}

pub unsafe extern "C" fn nac3_rc_decr(ptr: *mut u8) {
    let rc_ptr = ptr.cast::<usize>().sub(1);
    *rc_ptr -= 1;

    if *ptr == 0 {
        nac3_free(ptr);
    }
}

pub unsafe fn nac3_free(ptr: *mut u8) {
    let size_ptr = ptr.sub(2 * mem::size_of::<usize>()).cast::<usize>();

    dealloc(
        size_ptr.cast::<u8>(),
        Layout::from_size_align_unchecked(*size_ptr + 2 * mem::size_of::<usize>(), 8),
    );
}
