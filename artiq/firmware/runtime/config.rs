use std::cmp;
use std::vec::Vec;
use std::string::String;
use libc::{c_void, c_char, c_int, c_uint};

extern {
    fn fs_remove(key: *const c_char);
    fn fs_erase();
    fn fs_write(key: *const c_char, buffer: *const c_void, buflen: c_uint) -> c_int;
    fn fs_read(key: *const c_char, buffer: *mut c_void, buflen: c_uint,
               remain: *mut c_uint) -> c_uint;
}

macro_rules! c_str {
    ($s:ident) => {
        {
            let mut c = [0; 64 + 1];
            let len = cmp::min($s.len(), c.len() - 1);
            c[..len].copy_from_slice($s.as_bytes());
            c
        }
    }
}

pub fn read(key: &str, buf: &mut [u8]) -> Result<usize, usize> {
    let key_c = c_str!(key);
    let mut remain: c_uint = 0;
    let result = unsafe {
        fs_read(key_c.as_ptr() as *const c_char,
                buf.as_mut_ptr() as *mut c_void, buf.len() as c_uint, &mut remain)
    };
    if remain == 0 { Ok(result as usize) } else { Err(remain as usize) }
}

pub fn read_to_end(key: &str) -> Vec<u8> {
    let mut value = Vec::new();
    match read(key, &mut []) {
        Ok(0) => (),
        Ok(_) => unreachable!(),
        Err(size) => {
            value.resize(size, 0);
            read(key, &mut value).unwrap();
        }
    }
    value
}

pub fn read_string(key: &str) -> String {
    String::from_utf8(read_to_end(key)).unwrap()
}

pub fn write(key: &str, buf: &[u8]) -> Result<(), ()> {
    let key_c = c_str!(key);
    let result = unsafe {
        fs_write(key_c.as_ptr() as *const c_char,
                 buf.as_ptr() as *mut c_void, buf.len() as c_uint)
    };
    if result == 1 { Ok(()) } else { Err(()) }
}

pub fn remove(key: &str) {
    let key_c = c_str!(key);
    unsafe { fs_remove(key_c.as_ptr() as *const c_char) }
}

pub fn erase() {
    unsafe { fs_erase() }
}
