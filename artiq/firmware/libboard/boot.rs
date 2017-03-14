use irq;

pub unsafe fn reboot() -> ! {
    irq::set_ie(false);
    #[cfg(target_arch="or1k")]
    asm!(r#"
        l.j        _ftext
        l.nop
    "# : : : : "volatile");
    loop {}
}

pub unsafe fn hotswap(new_code: &[u8]) -> ! {
    irq::set_ie(false);
    #[cfg(target_arch="or1k")]
    asm!(r#"
        # This loop overwrites itself, but it's structured in such a way
        # that before that happens, it loads itself into I$$ fully.
        l.movhi    r4, hi(_ftext)
        l.ori      r4, r4, lo(_ftext)
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
    : "{r3}"(new_code.as_ptr() as usize),
      "{r5}"(new_code.len())
    :
    : "volatile");
    loop {}
}
