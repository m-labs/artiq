use super::{irq, cache};

pub unsafe fn jump(addr: usize) -> ! {
    irq::set_ie(false);
    cache::flush_cpu_icache();
    asm!(r#"
        l.jr    $0
         l.nop
    "# : : "r"(addr) : : "volatile");
    loop {}
}
