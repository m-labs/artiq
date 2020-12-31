#[cfg(has_ddrphy)]
mod ddr {
    use core::{ptr, fmt};
    use csr::{dfii, ddrphy};
    use sdram_phy::{self, spin_cycles};
    use sdram_phy::{DFII_COMMAND_CS, DFII_COMMAND_WE, DFII_COMMAND_CAS, DFII_COMMAND_RAS,
                    DFII_COMMAND_WRDATA, DFII_COMMAND_RDDATA};
    use sdram_phy::{DFII_NPHASES, DFII_PIX_DATA_SIZE, DFII_PIX_WRDATA_ADDR, DFII_PIX_RDDATA_ADDR};

    #[cfg(kusddrphy)]
    const DDRPHY_MAX_DELAY: u16 = 512;
    #[cfg(not(kusddrphy))]
    const DDRPHY_MAX_DELAY: u16 = 32;

    const DQS_SIGNAL_COUNT: usize = DFII_PIX_DATA_SIZE / 2;

    macro_rules! log {
        ($logger:expr, $( $arg:expr ),+) => (
            if let &mut Some(ref mut f) = $logger {
                let _ = write!(f, $( $arg ),+);
            }
        )
    }

    #[cfg(ddrphy_wlevel)]
    unsafe fn enable_write_leveling(enabled: bool) {
        dfii::pi0_address_write(sdram_phy::DDR3_MR1 as u16 | ((enabled as u16) << 7));
        dfii::pi0_baddress_write(1);
        sdram_phy::command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS);
        ddrphy::wlevel_en_write(enabled as u8);
    }

    #[cfg(ddrphy_wlevel)]
    unsafe fn write_level_scan(logger: &mut Option<&mut fmt::Write>) {
        #[cfg(kusddrphy)]
        log!(logger, "DQS initial delay: {} taps\n", ddrphy::wdly_dqs_taps_read());
        log!(logger, "Write leveling scan:\n");

        enable_write_leveling(true);
        spin_cycles(100);

        #[cfg(not(kusddrphy))]
        let ddrphy_max_delay : u16 = DDRPHY_MAX_DELAY;
        #[cfg(kusddrphy)]
        let ddrphy_max_delay : u16 = DDRPHY_MAX_DELAY - ddrphy::wdly_dqs_taps_read();

        for n in 0..DQS_SIGNAL_COUNT {
            let dq_addr = dfii::PI0_RDDATA_ADDR
                               .offset((DQS_SIGNAL_COUNT - 1 - n) as isize);

            log!(logger, "Module {}:\n", DQS_SIGNAL_COUNT - 1 - n);

            ddrphy::dly_sel_write(1 << n);

            ddrphy::wdly_dq_rst_write(1);
            ddrphy::wdly_dqs_rst_write(1);
            #[cfg(kusddrphy)]
            for _ in 0..ddrphy::wdly_dqs_taps_read() {
                ddrphy::wdly_dqs_inc_write(1);
            }

            let mut dq;
            for _ in 0..ddrphy_max_delay {
                ddrphy::wlevel_strobe_write(1);
                spin_cycles(10);
                dq = ptr::read_volatile(dq_addr);
                if dq != 0 {
                    log!(logger, "1");
                }
                else {
                    log!(logger, "0");
                }

                ddrphy::wdly_dq_inc_write(1);
                ddrphy::wdly_dqs_inc_write(1);
            }

            log!(logger, "\n");
        }

        enable_write_leveling(false);
    }

    #[cfg(ddrphy_wlevel)]
    unsafe fn write_level(logger: &mut Option<&mut fmt::Write>,
                          delay: &mut [u16; DQS_SIGNAL_COUNT],
                          high_skew: &mut [bool; DQS_SIGNAL_COUNT]) -> bool {
        #[cfg(kusddrphy)]
        log!(logger, "DQS initial delay: {} taps\n", ddrphy::wdly_dqs_taps_read());
        log!(logger, "Write leveling: ");

        enable_write_leveling(true);
        spin_cycles(100);

        #[cfg(not(kusddrphy))]
        let ddrphy_max_delay : u16 = DDRPHY_MAX_DELAY;
        #[cfg(kusddrphy)]
        let ddrphy_max_delay : u16 = DDRPHY_MAX_DELAY - ddrphy::wdly_dqs_taps_read();

        let mut failed = false;
        for n in 0..DQS_SIGNAL_COUNT {
            let dq_addr = dfii::PI0_RDDATA_ADDR
                               .offset((DQS_SIGNAL_COUNT - 1 - n) as isize);

            delay[n] = 0;
            high_skew[n] = false;

            ddrphy::dly_sel_write(1 << n);

            ddrphy::wdly_dq_rst_write(1);
            ddrphy::wdly_dqs_rst_write(1);
            #[cfg(kusddrphy)]
            for _ in 0..ddrphy::wdly_dqs_taps_read() {
                ddrphy::wdly_dqs_inc_write(1);
            }
            ddrphy::wlevel_strobe_write(1);
            spin_cycles(10);

            let mut incr_delay = || {
                delay[n] += 1;
                if delay[n] >= ddrphy_max_delay {
                    failed = true;
                    return false
                }

                ddrphy::wdly_dq_inc_write(1);
                ddrphy::wdly_dqs_inc_write(1);
                ddrphy::wlevel_strobe_write(1);
                spin_cycles(10);

                true
            };

            let mut dq = ptr::read_volatile(dq_addr);

            if dq != 0 {
                // Assume this DQ group has between 1 and 2 bit times of skew.
                // Bring DQS into the CK=0 zone before continuing leveling.
                high_skew[n] = true;

                while dq != 0 {
                    if !incr_delay() { break }
                    dq = ptr::read_volatile(dq_addr);
                }

                // Get a bit further into the 0 zone
                #[cfg(kusddrphy)]
                for _ in 0..32 {
                    incr_delay();
                }
            }

            while dq == 0 {
                if !incr_delay() { break }
                dq = ptr::read_volatile(dq_addr);
            }
        }

        enable_write_leveling(false);

        for n in (0..DQS_SIGNAL_COUNT).rev() {
            log!(logger, "{}{} ", delay[n], if high_skew[n] { "*" } else { "" });
        }

        if !failed {
            log!(logger, "done\n")
        } else {
            log!(logger, "failed\n")
        }

        !failed
    }

    #[cfg(ddrphy_wlevel)]
    unsafe fn read_bitslip(logger: &mut Option<&mut fmt::Write>,
                           delay: &[u16; DQS_SIGNAL_COUNT],
                           high_skew: &[bool; DQS_SIGNAL_COUNT]) {
        let threshold_opt = delay.iter().zip(high_skew.iter())
            .filter_map(|(&delay, &high_skew)|
                if high_skew { Some(delay) } else { None })
            .min()
            .map(|threshold| threshold / 2);

        if let Some(threshold) = threshold_opt {
            log!(logger, "Read bitslip: ");

            for n in (0..DQS_SIGNAL_COUNT).rev() {
                if delay[n] > threshold {
                    ddrphy::dly_sel_write(1 << n);

                    #[cfg(kusddrphy)]
                    ddrphy::rdly_dq_bitslip_write(1);
                    #[cfg(not(kusddrphy))]
                    for _ in 0..3 {
                        ddrphy::rdly_dq_bitslip_write(1);
                    }

                    log!(logger, "{} ", n);
                }
            }

            log!(logger, "\n");
        }
    }

    unsafe fn read_level_scan(logger: &mut Option<&mut fmt::Write>) {
        log!(logger, "Read leveling scan:\n");

        // Generate pseudo-random sequence
        let mut prs = [0; DFII_NPHASES * DFII_PIX_DATA_SIZE];
        let mut prv = 42;
        for b in prs.iter_mut() {
            prv = 1664525 * prv + 1013904223;
            *b = prv as u8;
        }

        // Activate
        dfii::pi0_address_write(0);
        dfii::pi0_baddress_write(0);
        sdram_phy::command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CS);
        spin_cycles(15);

        // Write test pattern
        for p in 0..DFII_NPHASES {
            for offset in 0..DFII_PIX_DATA_SIZE {
                let addr = DFII_PIX_WRDATA_ADDR[p].offset(offset as isize);
                let data = prs[DFII_PIX_DATA_SIZE * p + offset];
                ptr::write_volatile(addr, data as u32);
            }
        }
        sdram_phy::dfii_piwr_address_write(0);
        sdram_phy::dfii_piwr_baddress_write(0);
        sdram_phy::command_pwr(DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS|
                               DFII_COMMAND_WRDATA);

        // Calibrate each DQ in turn
        sdram_phy::dfii_pird_address_write(0);
        sdram_phy::dfii_pird_baddress_write(0);
        for n in 0..DQS_SIGNAL_COUNT {
            log!(logger, "Module {}:\n", DQS_SIGNAL_COUNT - n - 1);

            ddrphy::dly_sel_write(1 << (DQS_SIGNAL_COUNT - n - 1));

            ddrphy::rdly_dq_rst_write(1);
            #[cfg(soc_platform = "kasli")]
            {
                for _ in 0..3 {
                    ddrphy::rdly_dq_bitslip_write(1);
                }
            }

            for _ in 0..DDRPHY_MAX_DELAY {
                let mut working = true;
                for _ in 0..256 {
                    sdram_phy::command_prd(DFII_COMMAND_CAS|DFII_COMMAND_CS|
                                           DFII_COMMAND_RDDATA);
                    spin_cycles(15);

                    for p in 0..DFII_NPHASES {
                        for &offset in [n, n + DQS_SIGNAL_COUNT].iter() {
                            let addr = DFII_PIX_RDDATA_ADDR[p].offset(offset as isize);
                            let data = prs[DFII_PIX_DATA_SIZE * p + offset];
                            if ptr::read_volatile(addr) as u8 != data {
                                working = false;
                            }
                        }
                    }
                }
                if working {
                    log!(logger, "1");
                }
                else {
                    log!(logger, "0");
                }
                ddrphy::rdly_dq_inc_write(1);
            }

            log!(logger, "\n");

        }

        // Precharge
        dfii::pi0_address_write(0);
        dfii::pi0_baddress_write(0);
        sdram_phy::command_p0(DFII_COMMAND_RAS|DFII_COMMAND_WE|DFII_COMMAND_CS);
        spin_cycles(15);
    }

    unsafe fn read_level(logger: &mut Option<&mut fmt::Write>) -> bool {
        log!(logger, "Read leveling: ");

        // Generate pseudo-random sequence
        let mut prs = [0; DFII_NPHASES * DFII_PIX_DATA_SIZE];
        let mut prv = 42;
        for b in prs.iter_mut() {
            prv = 1664525 * prv + 1013904223;
            *b = prv as u8;
        }

        // Activate
        dfii::pi0_address_write(0);
        dfii::pi0_baddress_write(0);
        sdram_phy::command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CS);
        spin_cycles(15);

        // Write test pattern
        for p in 0..DFII_NPHASES {
            for offset in 0..DFII_PIX_DATA_SIZE {
                let addr = DFII_PIX_WRDATA_ADDR[p].offset(offset as isize);
                let data = prs[DFII_PIX_DATA_SIZE * p + offset];
                ptr::write_volatile(addr, data as u32);
            }
        }
        sdram_phy::dfii_piwr_address_write(0);
        sdram_phy::dfii_piwr_baddress_write(0);
        sdram_phy::command_pwr(DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS|
                               DFII_COMMAND_WRDATA);

        // Calibrate each DQ in turn
        sdram_phy::dfii_pird_address_write(0);
        sdram_phy::dfii_pird_baddress_write(0);
        for n in 0..DQS_SIGNAL_COUNT {
            ddrphy::dly_sel_write(1 << (DQS_SIGNAL_COUNT - n - 1));

            // Find the first (min_delay) and last (max_delay) tap that bracket
            // the largest tap interval of correct reads.
            let mut min_delay = 0;
            let mut max_delay = 0;

            let mut first_valid = 0;
            let mut seen_valid = 0;
            let mut seen_invalid = 0;
            let mut max_seen_valid = 0;

            ddrphy::rdly_dq_rst_write(1);
            #[cfg(soc_platform = "kasli")]
            {
                for _ in 0..3 {
                    ddrphy::rdly_dq_bitslip_write(1);
                }
            }

            for delay in 0..DDRPHY_MAX_DELAY {
                let mut valid = true;
                for _ in 0..256 {
                    sdram_phy::command_prd(DFII_COMMAND_CAS|DFII_COMMAND_CS|
                                           DFII_COMMAND_RDDATA);
                    spin_cycles(15);

                    for p in 0..DFII_NPHASES {
                        for &offset in [n, n + DQS_SIGNAL_COUNT].iter() {
                            let addr = DFII_PIX_RDDATA_ADDR[p].offset(offset as isize);
                            let data = prs[DFII_PIX_DATA_SIZE * p + offset];
                            if ptr::read_volatile(addr) as u8 != data {
                                valid = false;
                            }
                        }
                    }
                }

                if valid {
                    if seen_valid == 0 {
                        first_valid = delay;
                    }
                    seen_valid += 1;
                    seen_invalid = 0;
                    if seen_valid > max_seen_valid {
                        min_delay = first_valid;
                        max_delay = delay;
                        max_seen_valid = seen_valid;
                    }
                } else {
                    seen_invalid += 1;
                    if seen_invalid >= DDRPHY_MAX_DELAY / 8 {
                        seen_valid = 0;
                    }
                }
                ddrphy::rdly_dq_inc_write(1);
            }

            if max_delay <= min_delay {
                log!(logger, "Zero window: {}: {}-{} ({})\n",
                     DQS_SIGNAL_COUNT - n - 1, min_delay, max_delay,
                     max_seen_valid);
                return false
            }
            if max_seen_valid <= 5 {
                log!(logger, "Small window: {}: {}-{} ({})\n",
                     DQS_SIGNAL_COUNT - n - 1, min_delay, max_delay,
                     max_seen_valid);
                return false
            }

            let mean_delay = (min_delay + max_delay) / 2;
            log!(logger, "{}+-{} ", mean_delay, max_seen_valid / 2);

            // Set delay to the middle
            ddrphy::rdly_dq_rst_write(1);
            #[cfg(soc_platform = "kasli")]
            {
                for _ in 0..3 {
                    ddrphy::rdly_dq_bitslip_write(1);
                }
            }
            for _ in 0..mean_delay {
                ddrphy::rdly_dq_inc_write(1);
            }
        }

        // Precharge
        dfii::pi0_address_write(0);
        dfii::pi0_baddress_write(0);
        sdram_phy::command_p0(DFII_COMMAND_RAS|DFII_COMMAND_WE|DFII_COMMAND_CS);
        spin_cycles(15);

        log!(logger, "done\n");
        true
    }

    pub unsafe fn level(logger: &mut Option<&mut fmt::Write>) -> bool {
        #[cfg(ddrphy_wlevel)]
        {
            let mut delay = [0; DQS_SIGNAL_COUNT];
            let mut high_skew = [false; DQS_SIGNAL_COUNT];
            write_level_scan(logger);
            if !write_level(logger, &mut delay, &mut high_skew) {
                return false
            }
            read_bitslip(logger, &delay, &high_skew);
        }

        read_level_scan(logger);
        if !read_level(logger) {
            return false
        }

        true
    }
}

use core::fmt;
use csr;
use sdram_phy;

pub unsafe fn init(mut _logger: Option<&mut fmt::Write>) -> bool {
    sdram_phy::initialize();

    #[cfg(has_ddrphy)]
    {
        #[cfg(kusddrphy)]
        csr::ddrphy::en_vtc_write(0);
        if !ddr::level(&mut _logger) {
            return false
        }
        #[cfg(kusddrphy)]
        csr::ddrphy::en_vtc_write(1);
    }

    csr::dfii::control_write(sdram_phy::DFII_CONTROL_SEL);

    true
}
