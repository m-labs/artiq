use super::{cache, pmp};
use riscv::register::*;

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

pub unsafe fn start_user(addr: usize) -> ! {
    pmp::enable_user_memory();
    mstatus::set_mpp(mstatus::MPP::User);
    mepc::write(addr);
    llvm_asm!(
        "mret"
        : : : : "volatile"
    );
    unreachable!()
}
