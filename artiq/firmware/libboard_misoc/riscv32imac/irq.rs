use core::{convert::TryFrom};
use riscv::register::mstatus;
use vexriscv::register::{vmim, vmip};

#[inline]
pub fn get_ie() -> bool {
    mstatus::read().mie()
}

#[inline]
pub fn set_ie(ie: bool) {
    unsafe {
        if ie {
            mstatus::set_mie()
        } else {
            mstatus::clear_mie()
        }
    }
}

#[inline]
pub fn get_mask() -> u32 {
    u32::try_from(vmim::read()).unwrap()
}

#[inline]
pub fn set_mask(mask: u32) {
    vmim::write(usize::try_from(mask).unwrap())
}

#[inline]
pub fn pending_mask() -> u32 {
    u32::try_from(vmip::read()).unwrap()
}

pub fn enable(irq: u32) {
    set_mask(get_mask() | (1 << irq))
}

pub fn disable(irq: u32) {
    set_mask(get_mask() & !(1 << irq))
}

pub fn is_pending(irq: u32) -> bool {
    get_mask() & (1 << irq) != 0
}
