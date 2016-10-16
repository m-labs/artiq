use core::{ptr, slice, str};
use core::slice::SliceExt;
use libc::{c_void, c_char, c_int, size_t};

#[allow(non_camel_case_types)]
#[repr(C)]
#[derive(Default)]
struct dyld_info {
    __opaque: [usize; 7]
}

extern {
    fn dyld_load(shlib: *const c_void, base: usize,
                 resolve: extern fn(*mut c_void, *const c_char) -> usize,
                 resolve_data: *mut c_void,
                 info: *mut dyld_info, error_out: *mut *const c_char) -> c_int;
    fn dyld_lookup(symbol: *const c_char, info: *const dyld_info) -> *const c_void;

    fn strlen(ptr: *const c_char) -> size_t;
}

pub struct Library {
    lower: dyld_info
}

impl Library {
    pub unsafe fn load<F>(shlib: &[u8], base: usize, mut resolve: F)
                -> Result<Library, &'static str>
            where F: Fn(&str) -> usize {
        extern fn wrapper<F>(data: *mut c_void, name: *const c_char) -> usize
                where F: Fn(&str) -> usize {
            unsafe {
                let f = data as *mut F;
                let name = slice::from_raw_parts(name as *const u8, strlen(name));
                (*f)(str::from_utf8_unchecked(name))
            }
        }

        let mut library = Library { lower: dyld_info::default() };
        let mut error: *const c_char = ptr::null();
        if dyld_load(shlib.as_ptr() as *const _, base,
                     wrapper::<F>, &mut resolve as *mut _ as *mut _,
                     &mut library.lower, &mut error) == 0 {
            let error = slice::from_raw_parts(error as *const u8, strlen(error));
            Err(str::from_utf8_unchecked(error))
        } else {
            Ok(library)
        }
    }

    pub unsafe fn lookup(&self, symbol: &str) -> usize {
        assert!(symbol.len() < 32);
        let mut buf = [0u8; 32];
        buf[0..symbol.as_bytes().len()].copy_from_slice(symbol.as_bytes());
        dyld_lookup(&buf as *const _ as *const c_char, &self.lower) as usize
    }
}
