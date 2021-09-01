use super::cache;

pub unsafe fn reset() -> ! {
    llvm_asm!(r#"
        j          _reset_handler
         nop
    "# : : : : "volatile");
    loop {}
}

pub unsafe fn jump(addr: usize) -> ! {
    cache::flush_cpu_icache();
    llvm_asm!(r#"
        jalr       x0, 0($0)
         nop
    "# : : "r"(addr) : : "volatile");
    loop {}
}
