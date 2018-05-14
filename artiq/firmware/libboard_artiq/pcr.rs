use board_misoc::spr::*;

bitflags! {
    pub struct Counters: u32 {
        const LA     = SPR_PCMR_LA;
        const SA     = SPR_PCMR_SA;
        const IF     = SPR_PCMR_IF;
        const DCM    = SPR_PCMR_DCM;
        const ICM    = SPR_PCMR_ICM;
        const IFS    = SPR_PCMR_IFS;
        const LSUS   = SPR_PCMR_LSUS;
        const BS     = SPR_PCMR_BS;
        const DTLBM  = SPR_PCMR_DTLBM;
        const ITLBM  = SPR_PCMR_ITLBM;
        const DDS    = SPR_PCMR_DDS;

        const INSTRN = Self::IF.bits;
        const MEMORY = Self::LA.bits    | Self::SA.bits;
        const STALL  = Self::DCM.bits   | Self::ICM.bits   | Self::IFS.bits |
                       Self::LSUS.bits  | Self::BS.bits    | Self::DDS.bits ;
        const MISS   = Self::DTLBM.bits | Self::ITLBM.bits ;
    }
}

fn is_valid(index: u32) -> bool {
    index < 8 && unsafe { mfspr(SPR_PCMR0 + index) } & SPR_PCMR_CP != 0
}

#[inline]
pub fn setup(index: u32, counters: Counters) {
    debug_assert!(is_valid(index));

    unsafe {
        mtspr(SPR_PCMR0 + index, SPR_PCMR_CISM | SPR_PCMR_CIUM | counters.bits);
        mtspr(SPR_PCCR0 + index, 0);
    }
}

#[inline]
pub fn read(index: u32) -> u32 {
    unsafe {
        mfspr(SPR_PCCR0 + index)
    }
}
