#![feature(allocator)]
#![no_std]
#![allocator]

#[no_mangle]
pub extern "C" fn __rust_allocate(_size: usize, _align: usize) -> *mut u8 {
    unimplemented!()
}

#[no_mangle]
pub extern fn __rust_allocate_zeroed(_size: usize, _align: usize) -> *mut u8 {
    unimplemented!()
}

#[no_mangle]
pub extern "C" fn __rust_deallocate(_ptr: *mut u8, _old_size: usize, _align: usize) {
    unimplemented!()
}

#[no_mangle]
pub extern "C" fn __rust_reallocate(_ptr: *mut u8,
                                    _old_size: usize,
                                    _size: usize,
                                    _align: usize)
                                    -> *mut u8 {
    unimplemented!()
}

#[no_mangle]
pub extern "C" fn __rust_reallocate_inplace(_ptr: *mut u8,
                                            _old_size: usize,
                                            _size: usize,
                                            _align: usize)
                                            -> usize {
    unimplemented!()
}

#[no_mangle]
pub extern "C" fn __rust_usable_size(_size: usize, _align: usize) -> usize {
    unimplemented!()
}
