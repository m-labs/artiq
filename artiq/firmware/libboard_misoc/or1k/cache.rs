#[cfg(has_ddrphy)]
use core::ptr;
use super::spr::*;
#[cfg(has_ddrphy)]
use csr;
#[cfg(has_ddrphy)]
use mem;

pub fn flush_cpu_icache() {
    unsafe {
        let iccfgr = mfspr(SPR_ICCFGR);
        let ways = 1 << (iccfgr & SPR_ICCFGR_NCW);
        let set_size = 1 << ((iccfgr & SPR_ICCFGR_NCS) >> 3);
        let block_size = if iccfgr & SPR_ICCFGR_CBS != 0 { 32 } else { 16 };
        let size = set_size * ways * block_size;

        let mut i = 0;
        while i < size {
            mtspr(SPR_ICBIR, i);
            i += block_size;
        }
    }
}

pub fn flush_cpu_dcache() {
    unsafe {
        let dccfgr = mfspr(SPR_DCCFGR);
        let ways = 1 << (dccfgr & SPR_ICCFGR_NCW);
        let set_size = 1 << ((dccfgr & SPR_DCCFGR_NCS) >> 3);
        let block_size = if dccfgr & SPR_DCCFGR_CBS != 0 { 32 } else { 16 };
        let size = set_size * ways * block_size;

        let mut i = 0;
        while i < size {
            mtspr(SPR_DCBIR, i);
            i += block_size;
        }
    }
}

#[cfg(has_ddrphy)]
pub fn flush_l2_cache() {
    unsafe {
        for i in 0..2 * (csr::CONFIG_L2_SIZE as usize) / 4 {
            let addr = mem::MAIN_RAM_BASE + i * 4;
            ptr::read_volatile(addr as *const usize);
        }
    }
}
