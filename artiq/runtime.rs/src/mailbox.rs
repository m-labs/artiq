use core::ptr::{read_volatile, write_volatile};
use board;

const MAILBOX: *mut usize = board::mem::MAILBOX_BASE as *mut usize;
static mut last: usize = 0;

pub unsafe fn send(data: usize) {
    last = data;
    write_volatile(MAILBOX, data)
}

pub fn acknowledged() -> bool {
    unsafe {
        let data = read_volatile(MAILBOX);
        data == 0 || data != last
    }
}

pub fn receive() -> usize {
    unsafe {
        let data = read_volatile(MAILBOX);
        if data == last {
            0
        } else {
            if data != 0 {
                board::flush_cpu_dcache()
            }
            data
        }
    }
}

pub fn acknowledge() {
    unsafe { write_volatile(MAILBOX, 0) }
}
