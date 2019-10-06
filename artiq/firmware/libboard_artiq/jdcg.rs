use board_misoc::csr;

pub fn jesd_reset(reset: bool) {
    unsafe {
        csr::jesd_crg::jreset_write(if reset {1} else {0});
    }
}

pub fn jesd_enable(dacno: u8, en: bool) {
    unsafe {
        (csr::JDCG[dacno as usize].jesd_control_enable_write)(if en {1} else {0})
    }
}

pub fn jesd_ready(dacno: u8) -> bool {
    unsafe {
        (csr::JDCG[dacno as usize].jesd_control_ready_read)() != 0
    }
}

pub fn jesd_prbs(dacno: u8, en: bool) {
    unsafe {
        (csr::JDCG[dacno as usize].jesd_control_prbs_config_write)(if en {0b01} else {0b00})
    }
}

pub fn jesd_stpl(dacno: u8, en: bool) {
    unsafe {
        (csr::JDCG[dacno as usize].jesd_control_stpl_enable_write)(if en {1} else {0})
    }
}

pub fn jesd_jsync(dacno: u8) -> bool {
    unsafe {
        (csr::JDCG[dacno as usize].jesd_control_jsync_read)() != 0
    }
}
