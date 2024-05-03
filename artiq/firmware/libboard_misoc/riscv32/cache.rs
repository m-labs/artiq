#[cfg(has_ddrphy)]
use core::ptr;
#[cfg(has_ddrphy)]
use csr;
#[cfg(has_ddrphy)]
use mem;

pub fn flush_cpu_icache() {
    unsafe {
        asm!(
            "fence.i",
            "nop",
            "nop",
            "nop",
            "nop",
            "nop",
            options(preserves_flags, nostack)
        );
    }
}

pub fn flush_cpu_dcache() {
    unsafe {
        asm!(
            ".word(0x500F)",
            options(preserves_flags)
        );
    }
}

#[cfg(has_ddrphy)]
pub fn flush_l2_cache() {
    unsafe {
        for i in 0..2 * (csr::CONFIG_L2_SIZE as usize) / 4 {
            let addr = mem::MAIN_RAM_BASE + i * 4;
            ptr::read_volatile(addr as *const usize);
        }
    }
}
