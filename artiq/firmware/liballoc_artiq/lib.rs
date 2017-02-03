#![feature(allocator)]
#![no_std]
#![allocator]

use core::{mem, ptr, cmp};

// The minimum alignment guaranteed by the architecture.
const MIN_ALIGN: usize = 4;

const MAGIC_FREE: usize = 0xDEADDEAD;
const MAGIC_BUSY: usize = 0xFEEDFEED;

#[derive(Debug)]
struct Header {
    magic: usize,
    size:  usize,
    next:  *mut Header
}

static mut ROOT: *mut Header = 0 as *mut _;

pub unsafe fn seed(ptr: *mut u8, size: usize) {
    let header_size = mem::size_of::<Header>();

    if size < header_size * 2 { return }

    let curr = ptr as *mut Header;
    (*curr).magic = MAGIC_FREE;
    (*curr).size  = size - header_size;
    (*curr).next  = ROOT;
    ROOT = curr;
}

#[no_mangle]
pub extern fn __rust_allocate(mut size: usize, align: usize) -> *mut u8 {
    assert!(align <= MIN_ALIGN);

    let header_size = mem::size_of::<Header>();
    if size % header_size != 0 {
        size += header_size - (size % header_size);
    }

    unsafe {
        let mut curr = ROOT;
        while !curr.is_null() {
            match (*curr).magic {
                MAGIC_BUSY => (),
                MAGIC_FREE => {
                    let mut next = (*curr).next;
                    while !next.is_null() && (*next).magic == MAGIC_FREE {
                        // Join
                        (*next).magic = 0;
                        (*curr).size += (*next).size + header_size;
                        (*curr).next  = (*next).next;
                        next = (*curr).next;
                    }

                    if (*curr).size > size + header_size * 2 {
                        // Split
                        let offset = header_size + size;
                        let next = (curr as *mut u8).offset(offset as isize) as *mut Header;
                        (*next).magic = MAGIC_FREE;
                        (*next).size  = (*curr).size - offset;
                        (*next).next  = (*curr).next;
                        (*curr).next  = next;
                        (*curr).size  = size;
                    }

                    if (*curr).size >= size {
                        (*curr).magic = MAGIC_BUSY;
                        return curr.offset(1) as *mut u8
                    }
                },
                _ => panic!("heap corruption detected at {:p}", curr)
            }

            curr = (*curr).next;
        }
    }

    ptr::null_mut()
}

#[no_mangle]
pub extern fn __rust_deallocate(ptr: *mut u8, _old_size: usize, _align: usize) {
    unsafe {
        let curr = (ptr as *mut Header).offset(-1);
        if (*curr).magic != MAGIC_BUSY {
            panic!("heap corruption detected at {:p}", curr)
        }
        (*curr).magic = MAGIC_FREE;
    }
}

#[no_mangle]
pub extern fn __rust_reallocate(ptr: *mut u8, old_size: usize, size: usize,
                                align: usize) -> *mut u8 {
    unsafe {
        let new_ptr = __rust_allocate(size, align);
        if !new_ptr.is_null() {
            ptr::copy_nonoverlapping(ptr, new_ptr, cmp::min(old_size, size));
            __rust_deallocate(ptr, old_size, align);
        }
        new_ptr
    }
}

#[no_mangle]
pub extern fn __rust_reallocate_inplace(_ptr: *mut u8, old_size: usize, _size: usize,
                                        _align: usize) -> usize {
    old_size
}

#[no_mangle]
pub extern fn __rust_usable_size(size: usize, _align: usize) -> usize {
    size
}
