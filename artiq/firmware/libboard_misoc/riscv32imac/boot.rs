use super::{irq, cache};

pub unsafe fn reset() -> ! {
    irq::set_ie(false);
    llvm_asm!(r#"
        j          _reset_handler
         nop
    "# : : : : "volatile");
    loop {}
}

pub unsafe fn jump(addr: usize) -> ! {
    irq::set_ie(false);
    cache::flush_cpu_icache();
    llvm_asm!(r#"
        jalr       x0, 0($0)
         nop
    "# : : "r"(addr) : : "volatile");
    loop {}
}

pub unsafe fn hotswap(firmware: &[u8]) -> ! {
    irq::set_ie(false);
    llvm_asm!(r#"
        # This loop overwrites itself, but it's structured in such a way
        # that before that happens, it loads itself into I$$ fully.
        lui        a1, %hi(_reset_handler)
        ori        a1, a1, %lo(_reset_handler)
        or         a4, a1, zero
    0:  bnez       a2, 1f
         nop
        jr         a4
         nop
    1:  lw         a3, 0(a0)
        sw         a3, 0(a1)
        addi       a0, a0, 4
        addi       a1, a1, 4
        addi       a2, a2, -4
        bnez       a2, 0b
         nop
    "#
    :
    : "{a0}"(firmware.as_ptr() as usize),
      "{a2}"(firmware.len())
    :
    : "volatile");
    loop {}
}
