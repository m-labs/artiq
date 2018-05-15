use core::{cmp, str};
use board_misoc::{csr, clock};

fn read_rtm_ident(buf: &mut [u8]) -> &str {
    unsafe {
        csr::rtm_identifier::address_write(0);
        let len = csr::rtm_identifier::data_read();
        let len = cmp::min(len, buf.len() as u8);
        for i in 0..len {
            csr::rtm_identifier::address_write(1 + i);
            buf[i as usize] = csr::rtm_identifier::data_read();
        }
        str::from_utf8_unchecked(&buf[..len as usize])
    }
}

unsafe fn debug_print(rtm: bool) {
    info!("AMC serwb settings:");
    info!("  bitslip: {}", csr::serwb_phy_amc::control_bitslip_read());
    info!("  ready: {}", csr::serwb_phy_amc::control_ready_read());
    info!("  error: {}", csr::serwb_phy_amc::control_error_read());

    if rtm {
        info!("RTM serwb settings:");
        info!("  bitslip: {}", csr::serwb_phy_rtm::control_bitslip_read());
        info!("  ready: {}", csr::serwb_phy_rtm::control_ready_read());
        info!("  error: {}", csr::serwb_phy_rtm::control_error_read());
    }
}

pub fn wait_init() {
    info!("waiting for AMC/RTM serwb bridge to be ready...");
    unsafe {
        csr::serwb_phy_amc::control_reset_write(1);
        while csr::serwb_phy_amc::control_ready_read() == 0 {
            if csr::serwb_phy_amc::control_error_read() == 1 {
                debug_print(false);
                warn!("AMC/RTM serwb bridge initialization failed, retrying.");
                csr::serwb_phy_amc::control_reset_write(1);
            }
        }
    }
    info!("done.");

    unsafe {
        info!("RTM to AMC Link test");
        csr::serwb_phy_amc::control_prbs_cycles_write(1<<20);
        csr::serwb_phy_amc::control_prbs_start_write(1);
        clock::spin_us(1000000);
        info!("{} errors", csr::serwb_phy_amc::control_prbs_errors_read());

        info!("AMC to RTM Link test");
        csr::serwb_phy_rtm::control_prbs_cycles_write(1<<20);
        csr::serwb_phy_rtm::control_prbs_start_write(1);
        clock::spin_us(1000000);
        info!("{} errors", csr::serwb_phy_rtm::control_prbs_errors_read());
    }

    // Try reading the magic number register on the other side of the bridge.
    let rtm_magic = unsafe {
        csr::rtm_magic::magic_read()
    };
    if rtm_magic != 0x5352544d {
        error!("incorrect RTM magic number: 0x{:08x}", rtm_magic);
        // proceed anyway
    }

    unsafe {
        debug_print(true);
    }

    info!("RTM gateware version {}", read_rtm_ident(&mut [0; 64]));
}
