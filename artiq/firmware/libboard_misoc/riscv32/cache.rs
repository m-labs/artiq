#[cfg(has_ddrphy)]
use core::ptr;
#[cfg(has_ddrphy)]
use csr;
#[cfg(has_ddrphy)]
use mem;

pub fn flush_cpu_icache() {
    unsafe {
        llvm_asm!(r#"
            fence.i
            nop
            nop
            nop
            nop
            nop
        "# : : : : "volatile");
    }
}

pub fn flush_cpu_dcache() {
    unsafe {
        llvm_asm!(".word(0x500F)" : : : : "volatile");
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
