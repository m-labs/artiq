pub mod jesd {
    use board_misoc::{csr, clock};

    pub fn reset(reset: bool) {
        unsafe {
            csr::jesd_crg::jreset_write(if reset {1} else {0});
        }
    }

    pub fn enable(dacno: u8, en: bool) {
        unsafe {
            (csr::JDCG[dacno as usize].jesd_control_enable_write)(if en {1} else {0})
        }
        clock::spin_us(5000);
    }

    pub fn ready(dacno: u8) -> bool {
        unsafe {
            (csr::JDCG[dacno as usize].jesd_control_ready_read)() != 0
        }
    }

    pub fn prbs(dacno: u8, en: bool) {
        unsafe {
            (csr::JDCG[dacno as usize].jesd_control_prbs_config_write)(if en {0b01} else {0b00})
        }
        clock::spin_us(5000);
    }

    pub fn stpl(dacno: u8, en: bool) {
        unsafe {
            (csr::JDCG[dacno as usize].jesd_control_stpl_enable_write)(if en {1} else {0})
        }
        clock::spin_us(5000);
    }

    pub fn jsync(dacno: u8) -> bool {
        unsafe {
            (csr::JDCG[dacno as usize].jesd_control_jsync_read)() != 0
        }
    }
}

pub mod jdac {
    use board_misoc::{csr, clock};
    use board_artiq::drtioaux;

    use super::jesd;
    use super::super::jdac_requests;

    pub fn basic_request(dacno: u8, reqno: u8) {
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

            jesd::enable(dacno, true);
            clock::spin_us(10);
            if !jesd::ready(dacno) {
                error!("JESD core reported not ready");
            }

            basic_request(dacno, jdac_requests::INIT);

            jesd::prbs(dacno, true);
            basic_request(dacno, jdac_requests::PRBS);
            jesd::prbs(dacno, false);

            jesd::stpl(dacno, true);
            basic_request(dacno, jdac_requests::STPL);
            jesd::stpl(dacno, false);

            basic_request(dacno, jdac_requests::INIT);
            clock::spin_us(5000);

            basic_request(dacno, jdac_requests::PRINT_STATUS);

            if !jesd::jsync(dacno) {
                error!("JESD core reported bad SYNC");
            }

            info!("  ...done");
        }
    }
}

pub mod jesd204sync {
    fn sysref_auto_rtio_align() -> Result<(), &'static str> {
        info!("TODO: sysref_auto_rtio_align");
        Ok(())
    }

    fn sysref_auto_dac_align() -> Result<(), &'static str> {
        info!("TODO: sysref_auto_dac_align");
        Ok(())
    }

    pub fn sysref_auto_align() {
        if let Err(e) = sysref_auto_rtio_align() {
            error!("failed to align SYSREF at FPGA: {}", e);
        }
        if let Err(e) = sysref_auto_dac_align() {
            error!("failed to align SYSREF at DAC: {}", e);
        }
    }
}
