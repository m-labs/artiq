use core::ptr::{read_volatile, write_volatile};
use board;

const MAILBOX: *mut u32 = board::mem::MAILBOX_BASE as *mut u32;
static mut last: u32 = 0;

pub fn send(data: u32) {
    unsafe {
        last = data;
        write_volatile(MAILBOX, data)
    }
}

pub fn acknowledged() -> bool {
    unsafe {
        let data = read_volatile(MAILBOX);
        data == 0 || data != last
    }
}

pub fn send_and_wait(data: u32) {
    send(data);
    while !acknowledged() {}
}

pub fn receive() -> u32 {
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

pub fn wait_and_receive() -> u32 {
    loop {
        let data = receive();
        if data != 0 {
            return data
        }
    }
}

pub fn acknowledge() {
    unsafe { write_volatile(MAILBOX, 0) }
}
