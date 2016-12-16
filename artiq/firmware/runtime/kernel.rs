use core::ptr;
use board::csr;
use mailbox;
use rpc_queue;

use kernel_proto::{KERNELCPU_EXEC_ADDRESS, KERNELCPU_LAST_ADDRESS, KSUPPORT_HEADER_SIZE};

pub unsafe fn start() {
    if csr::kernel_cpu::reset_read() == 0 {
        panic!("attempted to start kernel CPU when it is already running")
    }

    stop();

    let ksupport_image = include_bytes!(concat!(env!("CARGO_TARGET_DIR"), "/../ksupport.elf"));
    let ksupport_addr = (KERNELCPU_EXEC_ADDRESS - KSUPPORT_HEADER_SIZE) as *mut u8;
    ptr::copy_nonoverlapping(ksupport_image.as_ptr(), ksupport_addr, ksupport_image.len());

    csr::kernel_cpu::reset_write(0);

    rpc_queue::init();
}

pub unsafe fn stop() {
    csr::kernel_cpu::reset_write(1);

    mailbox::acknowledge();
    rpc_queue::init();
}

pub fn validate(ptr: usize) -> bool {
    ptr >= KERNELCPU_EXEC_ADDRESS && ptr <= KERNELCPU_LAST_ADDRESS
}
