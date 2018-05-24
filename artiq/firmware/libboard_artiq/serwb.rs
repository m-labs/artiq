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

fn prbs_test() {
    let prbs_test_cycles : u32 = 1<<22;
    let prbs_test_us : u64 = ((prbs_test_cycles as u64)*40)/125; // 40 bits @125MHz linerate

    unsafe {
        info!("RTM to AMC Link test");
        csr::serwb_phy_amc::control_prbs_cycles_write(prbs_test_cycles);
        csr::serwb_phy_amc::control_prbs_start_write(1);
        clock::spin_us(prbs_test_us*110/100); // PRBS test time + 10%
        info!("{} errors", csr::serwb_phy_amc::control_prbs_errors_read());

        info!("AMC to RTM Link test");
        csr::serwb_phy_rtm::control_prbs_cycles_write(prbs_test_cycles);
        csr::serwb_phy_rtm::control_prbs_start_write(1);
        clock::spin_us(prbs_test_us*110/100); // PRBS test time + 10%
        info!("{} errors", csr::serwb_phy_rtm::control_prbs_errors_read());
    }
}

fn prng32(seed: &mut u32) -> u32 { *seed = 1664525 * *seed + 1013904223; *seed }

fn wishbone_test() {
    let test_length: u32 = 512;
    let mut test_errors : u32 = 0;

    let mut seed : u32;

    info!("Wishbone test...");
    unsafe {
        // Alternate pseudo random write/read bursts of
        // increasing size.
        for length in 0..test_length {
            // Pseudo random writes
            seed = length;
            for _ in 0..length {
                csr::rtm_scratch::write_data_write(prng32(&mut seed));
                csr::rtm_scratch::write_stb_write(1);
            }
            // Pseudo random reads
            seed = length;
            for _ in 0..length {
                if csr::rtm_scratch::read_data_read() != prng32(&mut seed) {
                    test_errors += 1;
                }
                csr::rtm_scratch::read_ack_write(1);
            }
        }
    }
    info!("{} errors", test_errors);
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

    // PRBS test
    prbs_test();

    // Wishbone test
    wishbone_test();

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
