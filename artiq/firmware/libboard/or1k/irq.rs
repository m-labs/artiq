use core::{fmt, convert};

use super::spr::*;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Exception {
    Reset = 0x1,
    BusError = 0x2,
    DataPageFault = 0x3,
    InsnPageFault = 0x4,
    Tick = 0x5,
    Alignment = 0x6,
    IllegalInsn = 0x7,
    Interrupt = 0x8,
    DtlbMiss = 0x9,
    ItlbMiss = 0xa,
    Range = 0xb,
    Syscall = 0xc,
    FloatingPoint = 0xd,
    Trap = 0xe,
}

impl fmt::Display for Exception {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match *self {
            Exception::Reset         => write!(f, "reset"),
            Exception::BusError      => write!(f, "bus error"),
            Exception::DataPageFault => write!(f, "data page fault"),
            Exception::InsnPageFault => write!(f, "instruction page fault"),
            Exception::Tick          => write!(f, "tick"),
            Exception::Alignment     => write!(f, "alignment"),
            Exception::IllegalInsn   => write!(f, "illegal instruction"),
            Exception::Interrupt     => write!(f, "interrupt"),
            Exception::DtlbMiss      => write!(f, "D-TLB miss"),
            Exception::ItlbMiss      => write!(f, "I-TLB miss"),
            Exception::Range         => write!(f, "range"),
            Exception::Syscall       => write!(f, "system call"),
            Exception::FloatingPoint => write!(f, "floating point"),
            Exception::Trap          => write!(f, "trap"),
        }
    }
}

impl convert::TryFrom<u32> for Exception {
    type Error = ();

    fn try_from(num: u32) -> Result<Self, Self::Error> {
        match num {
            0x1 => Ok(Exception::Reset),
            0x2 => Ok(Exception::BusError),
            0x3 => Ok(Exception::DataPageFault),
            0x4 => Ok(Exception::InsnPageFault),
            0x5 => Ok(Exception::Tick),
            0x6 => Ok(Exception::Alignment),
            0x7 => Ok(Exception::IllegalInsn),
            0x8 => Ok(Exception::Interrupt),
            0x9 => Ok(Exception::DtlbMiss),
            0xa => Ok(Exception::ItlbMiss),
            0xb => Ok(Exception::Range),
            0xc => Ok(Exception::Syscall),
            0xd => Ok(Exception::FloatingPoint),
            0xe => Ok(Exception::Trap),
            _ => Err(())
        }
    }
}

#[inline]
pub fn get_ie() -> bool {
    unsafe { mfspr(SPR_SR) & SPR_SR_IEE != 0 }
}

#[inline]
pub fn set_ie(ie: bool) {
    if ie {
        unsafe { mtspr(SPR_SR, mfspr(SPR_SR) | SPR_SR_IEE) }
    } else {
        unsafe { mtspr(SPR_SR, mfspr(SPR_SR) & !SPR_SR_IEE) }
    }
}

#[inline]
pub fn get_mask() -> u32 {
    unsafe { mfspr(SPR_PICMR) }
}

#[inline]
pub fn set_mask(mask: u32) {
    unsafe { mtspr(SPR_PICMR, mask) }
}

#[inline]
pub fn pending_mask() -> u32 {
    unsafe { mfspr(SPR_PICSR) }
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
