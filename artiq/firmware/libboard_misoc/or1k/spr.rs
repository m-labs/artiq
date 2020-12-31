#[inline(always)]
pub unsafe fn mfspr(reg: u32) -> u32 {
    let value: u32;
    asm!("l.mfspr $0, $1, 0" : "=r"(value) : "r"(reg) : : "volatile");
    value
}

#[inline(always)]
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

/* Data MMU group */
pub const SPR_DMMUCR:       u32 = SPRGROUP_DMMU + 0;
pub const SPR_DTLBEIR:      u32 = SPRGROUP_DMMU + 2;

/* Instruction MMU group */
pub const SPR_IMMUCR:       u32 = SPRGROUP_IMMU + 0;
pub const SPR_ITLBEIR:      u32 = SPRGROUP_IMMU + 2;

/* Data cache group */
pub const SPR_DCCR:         u32 = SPRGROUP_DC + 0;
pub const SPR_DCBPR:        u32 = SPRGROUP_DC + 1;
pub const SPR_DCBFR:        u32 = SPRGROUP_DC + 2;
pub const SPR_DCBIR:        u32 = SPRGROUP_DC + 3;
pub const SPR_DCBWR:        u32 = SPRGROUP_DC + 4;
pub const SPR_DCBLR:        u32 = SPRGROUP_DC + 5;

/* Instruction cache group */
pub const SPR_ICCR:         u32 = SPRGROUP_IC + 0;
pub const SPR_ICBPR:        u32 = SPRGROUP_IC + 1;
pub const SPR_ICBIR:        u32 = SPRGROUP_IC + 2;
pub const SPR_ICBLR:        u32 = SPRGROUP_IC + 3;

// [snip]

/* Performance counters group */
pub const SPR_PCCR0:        u32 = SPRGROUP_PC + 0;
pub const SPR_PCCR1:        u32 = SPRGROUP_PC + 1;
pub const SPR_PCCR2:        u32 = SPRGROUP_PC + 2;
pub const SPR_PCCR3:        u32 = SPRGROUP_PC + 3;
pub const SPR_PCCR4:        u32 = SPRGROUP_PC + 4;
pub const SPR_PCCR5:        u32 = SPRGROUP_PC + 5;
pub const SPR_PCCR6:        u32 = SPRGROUP_PC + 6;
pub const SPR_PCCR7:        u32 = SPRGROUP_PC + 7;
pub const SPR_PCMR0:        u32 = SPRGROUP_PC + 8;
pub const SPR_PCMR1:        u32 = SPRGROUP_PC + 9;
pub const SPR_PCMR2:        u32 = SPRGROUP_PC + 10;
pub const SPR_PCMR3:        u32 = SPRGROUP_PC + 11;
pub const SPR_PCMR4:        u32 = SPRGROUP_PC + 12;
pub const SPR_PCMR5:        u32 = SPRGROUP_PC + 13;
pub const SPR_PCMR6:        u32 = SPRGROUP_PC + 14;
pub const SPR_PCMR7:        u32 = SPRGROUP_PC + 15;

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

/*
 * Bit definitions for Data Cache Control register
 *
 */
pub const SPR_DCCR_EW:      u32 = 0x000000ff;  /* Enable ways */

/*
 * Bit definitions for Insn Cache Control register
 *
 */
pub const SPR_ICCR_EW:      u32 = 0x000000ff;  /* Enable ways */

/*
 * Bit definitions for Data Cache Configuration Register
 *
 */
pub const SPR_DCCFGR_NCW:       u32 = 0x00000007;
pub const SPR_DCCFGR_NCS:       u32 = 0x00000078;
pub const SPR_DCCFGR_CBS:       u32 = 0x00000080;
pub const SPR_DCCFGR_CWS:       u32 = 0x00000100;
pub const SPR_DCCFGR_CCRI:      u32 = 0x00000200;
pub const SPR_DCCFGR_CBIRI:     u32 = 0x00000400;
pub const SPR_DCCFGR_CBPRI:     u32 = 0x00000800;
pub const SPR_DCCFGR_CBLRI:     u32 = 0x00001000;
pub const SPR_DCCFGR_CBFRI:     u32 = 0x00002000;
pub const SPR_DCCFGR_CBWBRI:    u32 = 0x00004000;

pub const SPR_DCCFGR_NCW_OFF:   u32 = 0;
pub const SPR_DCCFGR_NCS_OFF:   u32 = 3;
pub const SPR_DCCFGR_CBS_OFF:   u32 = 7;

/*
 * Bit definitions for Instruction Cache Configuration Register
 *
 */
pub const SPR_ICCFGR_NCW:       u32 = 0x00000007;
pub const SPR_ICCFGR_NCS:       u32 = 0x00000078;
pub const SPR_ICCFGR_CBS:       u32 = 0x00000080;
pub const SPR_ICCFGR_CCRI:      u32 = 0x00000200;
pub const SPR_ICCFGR_CBIRI:     u32 = 0x00000400;
pub const SPR_ICCFGR_CBPRI:     u32 = 0x00000800;
pub const SPR_ICCFGR_CBLRI:     u32 = 0x00001000;

pub const SPR_ICCFGR_NCW_OFF:   u32 = 0;
pub const SPR_ICCFGR_NCS_OFF:   u32 = 3;
pub const SPR_ICCFGR_CBS_OFF:   u32 = 7;

/*
 * Bit definitions for Data MMU Configuration Register
 *
 */
pub const SPR_DMMUCFGR_NTW:     u32 = 0x00000003;
pub const SPR_DMMUCFGR_NTS:     u32 = 0x0000001C;
pub const SPR_DMMUCFGR_NAE:     u32 = 0x000000E0;
pub const SPR_DMMUCFGR_CRI:     u32 = 0x00000100;
pub const SPR_DMMUCFGR_PRI:     u32 = 0x00000200;
pub const SPR_DMMUCFGR_TEIRI:   u32 = 0x00000400;
pub const SPR_DMMUCFGR_HTR:     u32 = 0x00000800;

pub const SPR_DMMUCFGR_NTW_OFF: u32 = 0;
pub const SPR_DMMUCFGR_NTS_OFF: u32 = 2;

/*
 * Bit definitions for Instruction MMU Configuration Register
 *
 */
pub const SPR_IMMUCFGR_NTW:     u32 = 0x00000003;
pub const SPR_IMMUCFGR_NTS:     u32 = 0x0000001C;
pub const SPR_IMMUCFGR_NAE:     u32 = 0x000000E0;
pub const SPR_IMMUCFGR_CRI:     u32 = 0x00000100;
pub const SPR_IMMUCFGR_PRI:     u32 = 0x00000200;
pub const SPR_IMMUCFGR_TEIRI:   u32 = 0x00000400;
pub const SPR_IMMUCFGR_HTR:     u32 = 0x00000800;

pub const SPR_IMMUCFGR_NTW_OFF: u32 = 0;
pub const SPR_IMMUCFGR_NTS_OFF: u32 = 2;

/*
 * Bit definitions for Performance counters mode registers
 *
 */
pub const SPR_PCMR_CP:    u32 = 0x00000001;  /* Counter present */
pub const SPR_PCMR_UMRA:  u32 = 0x00000002;  /* User mode read access */
pub const SPR_PCMR_CISM:  u32 = 0x00000004;  /* Count in supervisor mode */
pub const SPR_PCMR_CIUM:  u32 = 0x00000008;  /* Count in user mode */
pub const SPR_PCMR_LA:    u32 = 0x00000010;  /* Load access event */
pub const SPR_PCMR_SA:    u32 = 0x00000020;  /* Store access event */
pub const SPR_PCMR_IF:    u32 = 0x00000040;  /* Instruction fetch event*/
pub const SPR_PCMR_DCM:   u32 = 0x00000080;  /* Data cache miss event */
pub const SPR_PCMR_ICM:   u32 = 0x00000100;  /* Insn cache miss event */
pub const SPR_PCMR_IFS:   u32 = 0x00000200;  /* Insn fetch stall event */
pub const SPR_PCMR_LSUS:  u32 = 0x00000400;  /* LSU stall event */
pub const SPR_PCMR_BS:    u32 = 0x00000800;  /* Branch stall event */
pub const SPR_PCMR_DTLBM: u32 = 0x00001000;  /* DTLB miss event */
pub const SPR_PCMR_ITLBM: u32 = 0x00002000;  /* ITLB miss event */
pub const SPR_PCMR_DDS:   u32 = 0x00004000;  /* Data dependency stall event */
pub const SPR_PCMR_WPE:   u32 = 0x03ff8000;  /* Watchpoint events */
