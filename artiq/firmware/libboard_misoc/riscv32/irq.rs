use riscv::register::{mie, mstatus};

fn vmim_write(val: usize) {
    unsafe {
        asm!("csrw {csr}, {rs}", rs = in(reg) val, csr = const 0xBC0);
    }
}

fn vmim_read() -> usize {
    let r: usize;
    unsafe {
        asm!("csrr {rd}, {csr}", rd = out(reg) r, csr = const 0xBC0);
    }
    r
}

fn vmip_read() -> usize {
    let r: usize;
    unsafe {
        asm!("csrr {rd}, {csr}", rd = out(reg) r, csr = const 0xFC0);
    }
    r
}

pub fn enable_interrupts() {
    unsafe {
        mstatus::set_mie();
        mie::set_mext();
    }
}

pub fn disable_interrupts() {
    unsafe {
        mstatus::clear_mie();
        mie::clear_mext();
    }
}

pub fn enable(id: u32) {
    vmim_write(vmim_read() | (1 << id));
}

pub fn disable(id: u32) {
    vmim_write(vmim_read() & !(1 << id));
}

pub fn is_pending(id: u32) -> bool {
    (vmip_read() >> id) & 1 == 1
}
