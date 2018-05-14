use super::{irq, cache};

pub unsafe fn reset() -> ! {
    irq::set_ie(false);
    asm!(r#"
        l.j     _reset_handler
         l.nop
    "# : : : : "volatile");
    loop {}
}

pub unsafe fn jump(addr: usize) -> ! {
    irq::set_ie(false);
    cache::flush_cpu_icache();
    asm!(r#"
        l.jr    $0
         l.nop
    "# : : "r"(addr) : : "volatile");
    loop {}
}

pub unsafe fn hotswap(firmware: &[u8]) -> ! {
    irq::set_ie(false);
    asm!(r#"
        # This loop overwrites itself, but it's structured in such a way
        # that before that happens, it loads itself into I$$ fully.
        l.movhi    r4, hi(_reset_handler)
        l.ori      r4, r4, lo(_reset_handler)
        l.or       r7, r4, r0
    0:  l.sfnei    r5, 0
        l.bf       1f
         l.nop
        l.jr       r7
         l.nop
    1:  l.lwz      r6, 0(r3)
        l.sw       0(r4), r6
        l.addi     r3, r3, 4
        l.addi     r4, r4, 4
        l.addi     r5, r5, -4
        l.bf       0b
         l.nop
    "#
    :
    : "{r3}"(firmware.as_ptr() as usize),
      "{r5}"(firmware.len())
    :
    : "volatile");
    loop {}
}
