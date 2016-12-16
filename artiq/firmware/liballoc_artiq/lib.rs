#![feature(allocator, libc)]
#![no_std]
#![allocator]

// The minimum alignment guaranteed by the architecture.
const MIN_ALIGN: usize = 8;

#[no_mangle]
pub extern "C" fn __rust_allocate(size: usize, align: usize) -> *mut u8 {
    unsafe { imp::allocate(size, align) }
}

#[no_mangle]
pub extern "C" fn __rust_deallocate(ptr: *mut u8, old_size: usize, align: usize) {
    unsafe { imp::deallocate(ptr, old_size, align) }
}

#[no_mangle]
pub extern "C" fn __rust_reallocate(ptr: *mut u8,
                                    old_size: usize,
                                    size: usize,
                                    align: usize)
                                    -> *mut u8 {
    unsafe { imp::reallocate(ptr, old_size, size, align) }
}

#[no_mangle]
pub extern "C" fn __rust_reallocate_inplace(ptr: *mut u8,
                                            old_size: usize,
                                            size: usize,
                                            align: usize)
                                            -> usize {
    unsafe { imp::reallocate_inplace(ptr, old_size, size, align) }
}

#[no_mangle]
pub extern "C" fn __rust_usable_size(size: usize, align: usize) -> usize {
    imp::usable_size(size, align)
}

mod imp {
    extern crate libc;

    use core::cmp;
    use core::ptr;
    use MIN_ALIGN;

    pub unsafe fn allocate(size: usize, align: usize) -> *mut u8 {
        if align <= MIN_ALIGN {
            libc::malloc(size as libc::size_t) as *mut u8
        } else {
            aligned_malloc(size, align)
        }
    }

    unsafe fn aligned_malloc(_size: usize, _align: usize) -> *mut u8 {
        panic!("aligned_malloc not implemented")
    }

    pub unsafe fn reallocate(ptr: *mut u8, old_size: usize,
                             size: usize, align: usize) -> *mut u8 {
        if align <= MIN_ALIGN {
            libc::realloc(ptr as *mut libc::c_void, size as libc::size_t) as *mut u8
        } else {
            let new_ptr = allocate(size, align);
            if !new_ptr.is_null() {
                ptr::copy(ptr, new_ptr, cmp::min(size, old_size));
                deallocate(ptr, old_size, align);
            }
            new_ptr
        }
    }

    pub unsafe fn reallocate_inplace(_ptr: *mut u8, old_size: usize,
                                     _size: usize, _align: usize) -> usize {
        old_size
    }

    pub unsafe fn deallocate(ptr: *mut u8, _old_size: usize, _align: usize) {
        libc::free(ptr as *mut libc::c_void)
    }

    pub fn usable_size(size: usize, _align: usize) -> usize {
        size
    }
}
