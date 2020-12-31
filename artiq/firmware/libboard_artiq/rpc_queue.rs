use core::ptr::{read_volatile, write_volatile};
use core::slice;
use board_misoc::{mem, cache};

const SEND_MAILBOX: *mut usize = (mem::MAILBOX_BASE + 4) as *mut usize;
const RECV_MAILBOX: *mut usize = (mem::MAILBOX_BASE + 8) as *mut usize;

const QUEUE_BEGIN: usize = 0x40400000;
const QUEUE_END:   usize = 0x407fff80;
const QUEUE_CHUNK: usize = 0x1000;

pub unsafe fn init() {
    write_volatile(SEND_MAILBOX, QUEUE_BEGIN);
    write_volatile(RECV_MAILBOX, QUEUE_BEGIN);
}

fn next(mut addr: usize) -> usize {
    debug_assert!(addr % QUEUE_CHUNK == 0);
    debug_assert!(addr >= QUEUE_BEGIN && addr < QUEUE_END);

    addr += QUEUE_CHUNK;
    if addr >= QUEUE_END { addr = QUEUE_BEGIN }
    addr
}

pub fn empty() -> bool {
    unsafe { read_volatile(SEND_MAILBOX) == read_volatile(RECV_MAILBOX) }
}

pub fn full() -> bool {
    unsafe { next(read_volatile(SEND_MAILBOX)) == read_volatile(RECV_MAILBOX) }
}

pub fn enqueue<T, E, F>(f: F) -> Result<T, E>
        where F: FnOnce(&mut [u8]) -> Result<T, E> {
    debug_assert!(!full());

    unsafe {
        let slice = slice::from_raw_parts_mut(read_volatile(SEND_MAILBOX) as *mut u8, QUEUE_CHUNK);
        f(slice).and_then(|x| {
            write_volatile(SEND_MAILBOX, next(read_volatile(SEND_MAILBOX)));
            Ok(x)
        })
    }
}

pub fn dequeue<T, E, F>(f: F) -> Result<T, E>
        where F: FnOnce(&mut [u8]) -> Result<T, E> {
    debug_assert!(!empty());

    unsafe {
        cache::flush_cpu_dcache();
        let slice = slice::from_raw_parts_mut(read_volatile(RECV_MAILBOX) as *mut u8, QUEUE_CHUNK);
        f(slice).and_then(|x| {
            write_volatile(RECV_MAILBOX, next(read_volatile(RECV_MAILBOX)));
            Ok(x)
        })
    }
}
