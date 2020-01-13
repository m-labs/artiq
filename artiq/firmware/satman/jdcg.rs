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

    pub fn basic_request(dacno: u8, reqno: u8, param: u8) -> Result<u8, &'static str> {
        if let Err(e) = drtioaux::send(1, &drtioaux::Packet::JdacBasicRequest {
            destination: 0,
            dacno: dacno,
            reqno: reqno, 
            param: param
        }) {
            error!("aux packet error ({})", e);
            return Err("aux packet error while sending for JESD DAC basic request");
        }
        match drtioaux::recv_timeout(1, Some(1000)) {
            Ok(drtioaux::Packet::JdacBasicReply { succeeded, retval }) => {
                if succeeded {
                    Ok(retval)
                } else {
                    error!("JESD DAC basic request failed (dacno={}, reqno={})", dacno, reqno);
                    Err("remote error status to JESD DAC basic request")
                }
            },
            Ok(packet) => {
                error!("received unexpected aux packet: {:?}", packet);
                Err("unexpected aux packet in reply to JESD DAC basic request")
            },
            Err(e) => {
                error!("aux packet error ({})", e);
                Err("aux packet error while waiting for JESD DAC basic reply")
            }
        }
    }

    fn init_one(dacno: u8) -> Result<(), &'static str> {
        jesd::enable(dacno, true);
        clock::spin_us(10);
        if !jesd::ready(dacno) {
            error!("JESD core reported not ready");
            return Err("JESD core reported not ready");
        }

        basic_request(dacno, jdac_requests::INIT, 0)?;

        jesd::prbs(dacno, true);
        basic_request(dacno, jdac_requests::PRBS, 0)?;
        jesd::prbs(dacno, false);

        jesd::stpl(dacno, true);
        basic_request(dacno, jdac_requests::STPL, 0)?;
        jesd::stpl(dacno, false);

        basic_request(dacno, jdac_requests::INIT, 0)?;
        clock::spin_us(5000);

        basic_request(dacno, jdac_requests::PRINT_STATUS, 0)?;

        if !jesd::jsync(dacno) {
            error!("JESD core reported bad SYNC");
            return Err("JESD core reported bad SYNC");
        }

        Ok(())
    }

    pub fn init() {
        for dacno in 0..csr::JDCG.len() {
            let dacno = dacno as u8;
            info!("DAC-{} initializing...", dacno);
            match init_one(dacno) {
                Ok(()) => info!("  ...done"),
                Err(e) => error!("  ...failed: {}", e)
            }
        }
    }
}
