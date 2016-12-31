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
