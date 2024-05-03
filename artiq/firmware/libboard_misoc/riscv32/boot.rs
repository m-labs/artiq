use super::{cache, pmp};
use riscv::register::*;

pub unsafe fn reset() -> ! {
    asm!("j          _reset_handler",
         "nop",
         options(nomem, nostack, noreturn)
    );
}

pub unsafe fn jump(addr: usize) -> ! {
    cache::flush_cpu_icache();
    asm!("jalr       x0, 0({0})",
         "nop",
         in(reg) addr,
         options(nomem, nostack, noreturn)
    );
}

pub unsafe fn start_user(addr: usize) -> ! {
    pmp::enable_user_memory();
    mstatus::set_mpp(mstatus::MPP::User);
    mepc::write(addr);
    asm!("mret",
        options(nomem, nostack, noreturn)
    );
}
