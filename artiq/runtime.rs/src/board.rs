use core::{cmp, ptr, str};

include!(concat!(env!("BUILDINC_DIRECTORY"), "/generated/mem.rs"));
include!(concat!(env!("BUILDINC_DIRECTORY"), "/generated/csr.rs"));

pub fn ident(buf: &mut [u8]) -> &str {
    unsafe {
        let len = ptr::read_volatile(csr::IDENTIFIER_MEM_BASE);
        let len = cmp::min(len as usize, buf.len());
        for i in 0..len {
            buf[i] = ptr::read_volatile(csr::IDENTIFIER_MEM_BASE.offset(1 + i as isize)) as u8
        }
        str::from_utf8_unchecked(&buf[..len])
    }
}
