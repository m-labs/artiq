use board_misoc::{csr, clock};
use board_artiq::drtioaux;

pub fn jesd_reset(reset: bool) {
    unsafe {
        csr::jesd_crg::jreset_write(if reset {1} else {0});
    }
}

fn jesd_enable(dacno: u8, en: bool) {
    unsafe {
        (csr::JDCG[dacno as usize].jesd_control_enable_write)(if en {1} else {0})
    }
    clock::spin_us(5000);
}

fn jesd_ready(dacno: u8) -> bool {
    unsafe {
        (csr::JDCG[dacno as usize].jesd_control_ready_read)() != 0
    }
}

fn jesd_prbs(dacno: u8, en: bool) {
    unsafe {
        (csr::JDCG[dacno as usize].jesd_control_prbs_config_write)(if en {0b01} else {0b00})
    }
    clock::spin_us(5000);
}

fn jesd_stpl(dacno: u8, en: bool) {
    unsafe {
        (csr::JDCG[dacno as usize].jesd_control_stpl_enable_write)(if en {1} else {0})
    }
    clock::spin_us(5000);
}

fn jesd_jsync(dacno: u8) -> bool {
    unsafe {
        (csr::JDCG[dacno as usize].jesd_control_jsync_read)() != 0
    }
}

fn jdac_basic_request(dacno: u8, reqno: u8) {
    if let Err(e) = drtioaux::send(1, &drtioaux::Packet::JdacBasicRequest {
        destination: 0,
        dacno: dacno,
        reqno: reqno
    }) {
        error!("aux packet error ({})", e);
    }
    match drtioaux::recv_timeout(1, Some(1000)) {
        Ok(drtioaux::Packet::JdacBasicReply { succeeded }) =>
            if !succeeded {
                error!("JESD DAC basic request failed (dacno={}, reqno={})", dacno, reqno);
            },
        Ok(packet) => error!("received unexpected aux packet: {:?}", packet),
        Err(e) => error!("aux packet error ({})", e),
    }
}

pub fn init() {
    for dacno in 0..csr::JDCG.len() {
        let dacno = dacno as u8;
        info!("DAC-{} initializing...", dacno);

        jesd_enable(dacno, true);
        jesd_prbs(dacno, false);
        jesd_stpl(dacno, false);

        jdac_basic_request(dacno, 0);

        jesd_prbs(dacno, true);
        jdac_basic_request(dacno, 2);
        jesd_prbs(dacno, false);

        jesd_stpl(dacno, true);
        jdac_basic_request(dacno, 3);
        jesd_stpl(dacno, false);

        jdac_basic_request(dacno, 0);

        let t = clock::get_ms();
        while !jesd_ready(dacno) {
            if clock::get_ms() > t + 200 {
                error!("JESD ready timeout");
                break;
            }
        }
        clock::spin_us(5000);
        jdac_basic_request(dacno, 1);

        if !jesd_jsync(dacno) {
            error!("bad SYNC");
        }

        info!("  ...done");
    }
}
