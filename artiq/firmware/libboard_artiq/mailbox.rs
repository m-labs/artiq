use core::ptr::{read_volatile, write_volatile};
use board_misoc::{mem, cache};

const MAILBOX: *mut usize = mem::MAILBOX_BASE as *mut usize;
static mut LAST: usize = 0;

pub unsafe fn send(data: usize) {
    LAST = data;
    // after Rust toolchain update to LLVM12, this empty asm! block is required
    // to ensure that the compiler doesn't take any shortcuts
    // otherwise, the comm CPU will read garbage data and crash
    asm!("", options(preserves_flags, readonly, nostack));
    write_volatile(MAILBOX, data);
}

pub fn acknowledged() -> bool {
    unsafe {
        let data = read_volatile(MAILBOX);
        data == 0 || data != LAST
    }
}

pub fn receive() -> usize {
    unsafe {
        let data = read_volatile(MAILBOX);
        if data == LAST {
            0
        } else {
            if data != 0 {
                cache::flush_cpu_dcache()
            }
            data
        }
    }
}

pub fn acknowledge() {
    unsafe { write_volatile(MAILBOX, 0) }
}
