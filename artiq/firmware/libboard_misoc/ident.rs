use core::{cmp, str};
use csr;

pub fn read(buf: &mut [u8]) -> &str {
    unsafe {
        csr::identifier::address_write(0);
        let len = csr::identifier::data_read();
        let len = cmp::min(len, buf.len() as u8);
        for i in 0..len {
            csr::identifier::address_write(1 + i);
            buf[i as usize] = csr::identifier::data_read();
        }
        str::from_utf8_unchecked(&buf[..len as usize])
    }
}
