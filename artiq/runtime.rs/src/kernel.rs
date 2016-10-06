use core::ptr;
use board::csr;
use mailbox;

const KERNELCPU_EXEC_ADDRESS:    usize = 0x40400000;
const KERNELCPU_LAST_ADDRESS:    usize = (0x4fffffff - 1024*1024);
const KSUPPORT_HEADER_SIZE:      usize = 0x80;

pub unsafe fn start() {
    if csr::kernel_cpu::reset_read() == 0 {
        panic!("attempted to start kernel CPU when it is already running")
    }

    stop();

    extern {
        static _binary_ksupport_elf_start: u8;
        static _binary_ksupport_elf_end: u8;
    }
    let ksupport_start = &_binary_ksupport_elf_start as *const _;
    let ksupport_end   = &_binary_ksupport_elf_end as *const _;
    ptr::copy_nonoverlapping(ksupport_start,
                             (KERNELCPU_EXEC_ADDRESS - KSUPPORT_HEADER_SIZE) as *mut u8,
                             ksupport_end as usize - ksupport_start as usize);

    csr::kernel_cpu::reset_write(0);
}

pub fn stop() {
    unsafe { csr::kernel_cpu::reset_write(1) }
    mailbox::acknowledge();
}

pub fn validate(ptr: usize) -> bool {
    ptr >= KERNELCPU_EXEC_ADDRESS && ptr <= KERNELCPU_LAST_ADDRESS
}
