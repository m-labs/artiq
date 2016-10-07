#![allow(dead_code)]

use core::{cmp, ptr, str};

include!(concat!(env!("BUILDINC_DIRECTORY"), "/generated/mem.rs"));
include!(concat!(env!("BUILDINC_DIRECTORY"), "/generated/csr.rs"));

pub mod spr {
    pub unsafe fn mfspr(reg: u32) -> u32 {
        let value: u32;
        asm!("l.mfspr $0, $1, 0" : "=r"(value) : "r"(reg) : : "volatile");
        value
    }

    pub unsafe fn mtspr(reg: u32, value: u32) {
        asm!("l.mtspr $0, $1, 0" : : "r"(reg), "r"(value) : : "volatile")
    }

    /* Definition of special-purpose registers (SPRs). */

    pub const MAX_GRPS:         u32 = 32;
    pub const MAX_SPRS_PER_GRP_BITS: u32 = 11;
    pub const MAX_SPRS_PER_GRP: u32 = 1 << MAX_SPRS_PER_GRP_BITS;
    pub const MAX_SPRS:         u32 = 0x10000;

    /* Base addresses for the groups */
    pub const SPRGROUP_SYS:     u32 = 0 << MAX_SPRS_PER_GRP_BITS;
    pub const SPRGROUP_DMMU:    u32 = 1 << MAX_SPRS_PER_GRP_BITS;
    pub const SPRGROUP_IMMU:    u32 = 2 << MAX_SPRS_PER_GRP_BITS;
    pub const SPRGROUP_DC:      u32 = 3 << MAX_SPRS_PER_GRP_BITS;
    pub const SPRGROUP_IC:      u32 = 4 << MAX_SPRS_PER_GRP_BITS;
    pub const SPRGROUP_MAC:     u32 = 5 << MAX_SPRS_PER_GRP_BITS;
    pub const SPRGROUP_D:       u32 = 6 << MAX_SPRS_PER_GRP_BITS;
    pub const SPRGROUP_PC:      u32 = 7 << MAX_SPRS_PER_GRP_BITS;
    pub const SPRGROUP_PM:      u32 = 8 << MAX_SPRS_PER_GRP_BITS;
    pub const SPRGROUP_PIC:     u32 = 9 << MAX_SPRS_PER_GRP_BITS;
    pub const SPRGROUP_TT:      u32 = 10 << MAX_SPRS_PER_GRP_BITS;
    pub const SPRGROUP_FP:      u32 = 11 << MAX_SPRS_PER_GRP_BITS;

    /* System control and status group */
    pub const SPR_VR:           u32 = SPRGROUP_SYS + 0;
    pub const SPR_UPR:          u32 = SPRGROUP_SYS + 1;
    pub const SPR_CPUCFGR:      u32 = SPRGROUP_SYS + 2;
    pub const SPR_DMMUCFGR:     u32 = SPRGROUP_SYS + 3;
    pub const SPR_IMMUCFGR:     u32 = SPRGROUP_SYS + 4;
    pub const SPR_DCCFGR:       u32 = SPRGROUP_SYS + 5;
    pub const SPR_ICCFGR:       u32 = SPRGROUP_SYS + 6;
    pub const SPR_DCFGR:        u32 = SPRGROUP_SYS + 7;
    pub const SPR_PCCFGR:       u32 = SPRGROUP_SYS + 8;
    pub const SPR_VR2:          u32 = SPRGROUP_SYS + 9;
    pub const SPR_AVR:          u32 = SPRGROUP_SYS + 10;
    pub const SPR_EVBAR:        u32 = SPRGROUP_SYS + 11;
    pub const SPR_AECR:         u32 = SPRGROUP_SYS + 12;
    pub const SPR_AESR:         u32 = SPRGROUP_SYS + 13;
    pub const SPR_NPC:          u32 = SPRGROUP_SYS + 16;  /* CZ 21/06/01 */
    pub const SPR_SR:           u32 = SPRGROUP_SYS + 17;  /* CZ 21/06/01 */
    pub const SPR_PPC:          u32 = SPRGROUP_SYS + 18;  /* CZ 21/06/01 */
    pub const SPR_FPCSR:        u32 = SPRGROUP_SYS + 20;  /* CZ 21/06/01 */
    pub const SPR_ISR_BASE:     u32 = SPRGROUP_SYS + 21;
    pub const SPR_EPCR_BASE:    u32 = SPRGROUP_SYS + 32;  /* CZ 21/06/01 */
    pub const SPR_EPCR_LAST:    u32 = SPRGROUP_SYS + 47;  /* CZ 21/06/01 */
    pub const SPR_EEAR_BASE:    u32 = SPRGROUP_SYS + 48;
    pub const SPR_EEAR_LAST:    u32 = SPRGROUP_SYS + 63;
    pub const SPR_ESR_BASE:     u32 = SPRGROUP_SYS + 64;
    pub const SPR_ESR_LAST:     u32 = SPRGROUP_SYS + 79;
    pub const SPR_GPR_BASE:     u32 = SPRGROUP_SYS + 1024;

    // [snip]

    /* PIC group */
    pub const SPR_PICMR:        u32 = SPRGROUP_PIC + 0;
    pub const SPR_PICPR:        u32 = SPRGROUP_PIC + 1;
    pub const SPR_PICSR:        u32 = SPRGROUP_PIC + 2;

    // [snip]

    /*
     * Bit definitions for the Supervision Register
     *
     */
    pub const SPR_SR_SM:        u32 = 0x00000001;  /* Supervisor Mode */
    pub const SPR_SR_TEE:       u32 = 0x00000002;  /* Tick timer Exception Enable */
    pub const SPR_SR_IEE:       u32 = 0x00000004;  /* Interrupt Exception Enable */
    pub const SPR_SR_DCE:       u32 = 0x00000008;  /* Data Cache Enable */
    pub const SPR_SR_ICE:       u32 = 0x00000010;  /* Instruction Cache Enable */
    pub const SPR_SR_DME:       u32 = 0x00000020;  /* Data MMU Enable */
    pub const SPR_SR_IME:       u32 = 0x00000040;  /* Instruction MMU Enable */
    pub const SPR_SR_LEE:       u32 = 0x00000080;  /* Little Endian Enable */
    pub const SPR_SR_CE:        u32 = 0x00000100;  /* CID Enable */
    pub const SPR_SR_F:         u32 = 0x00000200;  /* Condition Flag */
    pub const SPR_SR_CY:        u32 = 0x00000400;  /* Carry flag */
    pub const SPR_SR_OV:        u32 = 0x00000800;  /* Overflow flag */
    pub const SPR_SR_OVE:       u32 = 0x00001000;  /* Overflow flag Exception */
    pub const SPR_SR_DSX:       u32 = 0x00002000;  /* Delay Slot Exception */
    pub const SPR_SR_EPH:       u32 = 0x00004000;  /* Exception Prefix High */
    pub const SPR_SR_FO:        u32 = 0x00008000;  /* Fixed one */
    pub const SPR_SR_SUMRA:     u32 = 0x00010000;  /* Supervisor SPR read access */
    pub const SPR_SR_RES:       u32 = 0x0ffe0000;  /* Reserved */
    pub const SPR_SR_CID:       u32 = 0xf0000000;  /* Context ID */

}

pub mod irq {
    use super::spr::*;

    pub fn get_ie() -> bool {
        unsafe { mfspr(SPR_SR) & SPR_SR_IEE != 0 }
    }

    pub fn set_ie(ie: bool) {
        if ie {
            unsafe { mtspr(SPR_SR, mfspr(SPR_SR) | SPR_SR_IEE) }
        } else {
            unsafe { mtspr(SPR_SR, mfspr(SPR_SR) & !SPR_SR_IEE) }
        }
    }

    pub fn get_mask() -> u32 {
        unsafe { mfspr(SPR_PICMR) }
    }

    pub fn set_mask(mask: u32) {
        unsafe { mtspr(SPR_PICMR, mask) }
    }

    pub fn pending() -> u32 {
        unsafe { mfspr(SPR_PICSR) }
    }
}

extern {
    pub fn flush_cpu_dcache();
    pub fn flush_l2_cache();
}

pub fn ident(buf: &mut [u8]) -> &str {
    unsafe {
        let len = ptr::read_volatile(csr::IDENTIFIER_MEM_BASE);
        let len = cmp::min(len as usize, buf.len());
        for i in 0..len {
            buf[i] = ptr::read_volatile(csr::IDENTIFIER_MEM_BASE.offset(1 + i as isize)) as u8
        }
        str::from_utf8_unchecked(&buf[..len])
    }
}
