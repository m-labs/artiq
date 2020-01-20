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
    }

    pub fn phy_done(dacno: u8) -> bool {
       unsafe {
           (csr::JDCG[dacno as usize].jesd_control_phy_done_read)() != 0
       }
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

    pub fn init() -> Result<(), &'static str> {
        for dacno in 0..csr::JDCG.len() {
            let dacno = dacno as u8;
            info!("DAC-{} initializing...", dacno);

            jesd::enable(dacno, true);
            clock::spin_us(10_000);
            if !jesd::phy_done(dacno) {
                error!("JESD core PHY not done");
                return Err("JESD core PHY not done");
            }

            basic_request(dacno, jdac_requests::INIT, 0)?;

            // JESD ready depends on JSYNC being valid, so DAC init needs to happen first
            if !jesd::ready(dacno) {
                error!("JESD core reported not ready, sending DAC status print request");
                basic_request(dacno, jdac_requests::PRINT_STATUS, 0)?;
                return Err("JESD core reported not ready");
            }

            jesd::prbs(dacno, true);
            basic_request(dacno, jdac_requests::PRBS, 0)?;
            jesd::prbs(dacno, false);

            jesd::stpl(dacno, true);
            basic_request(dacno, jdac_requests::STPL, 0)?;
            jesd::stpl(dacno, false);

            basic_request(dacno, jdac_requests::INIT, 0)?;
            clock::spin_us(5000);

            if !jesd::jsync(dacno) {
                error!("JESD core reported bad SYNC");
                return Err("JESD core reported bad SYNC");
            }

            info!("  ...done");
        }
        Ok(())
    }
}

pub mod jesd204sync {
    use board_misoc::{csr, clock, config};

    use super::jdac;
    use super::super::jdac_requests;

    const HMC7043_ANALOG_DELAY_RANGE: u8 = 24;

    const FPGA_CLK_DIV: u16 = 16;  // Keep in sync with hmc830_7043.rs
    const SYSREF_DIV: u16 = 256;   // Keep in sync with hmc830_7043.rs

    fn hmc7043_sysref_delay_dac(dacno: u8, phase_offset: u8) -> Result<(), &'static str> {
        match jdac::basic_request(dacno, jdac_requests::SYSREF_DELAY_DAC, phase_offset) {
            Ok(_) => Ok(()),
            Err(e) => Err(e)
        }
    }


    fn hmc7043_sysref_slip() -> Result<(), &'static str> {
        match jdac::basic_request(0, jdac_requests::SYSREF_SLIP, 0) {
            Ok(_) => Ok(()),
            Err(e) => Err(e)
        }
    }

    fn ad9154_sync(dacno: u8) -> Result<bool, &'static str> {
        match jdac::basic_request(dacno, jdac_requests::SYNC, 0) {
            Ok(0) => Ok(false),
            Ok(_) => Ok(true),
            Err(e) => Err(e)
        }
    }

    fn average_2phases(a: i32, b: i32, modulo: i32) -> i32 {
        let diff = ((a - b + modulo/2 + modulo) % modulo) - modulo/2;
        return (modulo + b + diff/2) % modulo;
    }

    fn average_phases(phases: &[i32], modulo: i32) -> i32 {
        if phases.len() == 1 {
            panic!("input array length must be a power of 2");
        } else if phases.len() == 2 {
            average_2phases(phases[0], phases[1], modulo)
        } else {
            let cut = phases.len()/2;
            average_2phases(
                average_phases(&phases[..cut], modulo),
                average_phases(&phases[cut..], modulo),
                modulo)
        }
    }

    const RAW_DDMTD_N_SHIFT: i32 = 6;
    const RAW_DDMTD_N: i32 = 1 << RAW_DDMTD_N_SHIFT;
    const DDMTD_DITHER_BITS: i32 = 1;
    const DDMTD_N_SHIFT: i32 = RAW_DDMTD_N_SHIFT + DDMTD_DITHER_BITS;
    const DDMTD_N: i32 = 1 << DDMTD_N_SHIFT;

    fn init_ddmtd() -> Result<(), &'static str> {
        unsafe {
            csr::sysref_ddmtd::reset_write(1);
            clock::spin_us(1);
            csr::sysref_ddmtd::reset_write(0);
            clock::spin_us(100);
            if csr::sysref_ddmtd::locked_read() != 0 {
                Ok(())
            } else {
                Err("DDMTD helper PLL failed to lock")
            }
        }
    }

    fn measure_ddmdt_phase_raw() -> i32 {
        unsafe { csr::sysref_ddmtd::dt_read() as i32 }
    }

    fn measure_ddmdt_phase() -> i32 {
        const AVG_PRECISION_SHIFT: i32 = 6;
        const AVG_PRECISION: i32 = 1 << AVG_PRECISION_SHIFT;
        const AVG_MOD: i32 = 1 << (RAW_DDMTD_N_SHIFT + AVG_PRECISION_SHIFT + DDMTD_DITHER_BITS);

        let mut measurements = [0; AVG_PRECISION as usize];
        for i in 0..AVG_PRECISION {
            measurements[i as usize] = measure_ddmdt_phase_raw() << (AVG_PRECISION_SHIFT + DDMTD_DITHER_BITS);
            clock::spin_us(10);
        }
        average_phases(&measurements, AVG_MOD) >> AVG_PRECISION_SHIFT
    }

    fn test_ddmtd_stability(raw: bool, tolerance: i32) -> Result<(), &'static str> {
        info!("testing DDMTD stability (raw={}, tolerance={})...", raw, tolerance);

        let modulo = if raw { RAW_DDMTD_N } else { DDMTD_N };
        let measurement = if raw { measure_ddmdt_phase_raw } else { measure_ddmdt_phase };
        let ntests = if raw { 15000 } else { 150 };

        let mut max_pkpk = 0;
        for _ in 0..32 {
            // If we are near the edges, wraparound can throw off the simple min/max computation.
            // In this case, add an offset to get near the center.
            let quadrant = measure_ddmdt_phase();
            let center_offset =
                if quadrant < DDMTD_N/4 || quadrant > 3*DDMTD_N/4 {
                    modulo/2
                } else {
                    0
                };

            let mut min = modulo;
            let mut max = 0;
            for _ in 0..ntests {
                let m = (measurement() + center_offset) % modulo;
                if m < min {
                    min = m;
                }
                if m > max {
                    max = m;
                }
            }
            let pkpk = max - min;
            if pkpk > max_pkpk {
                max_pkpk = pkpk;
            }
            if pkpk > tolerance {
                error!("  ...excessive peak-peak jitter: {} (min={} max={} center_offset={})", pkpk,
                    min, max, center_offset);
                return Err("excessive DDMTD peak-peak jitter");
            }
            hmc7043_sysref_slip();
        }

        info!("  ...passed, peak-peak jitter: {}", max_pkpk);
        Ok(())
    }

    fn test_slip_ddmtd() -> Result<(), &'static str> {
        // expected_step = (RTIO clock frequency)*(DDMTD N)/(HMC7043 CLKIN frequency)
        let expected_step = 8;
        let tolerance = 1;

        info!("testing HMC7043 SYSREF slip against DDMTD...");
        let mut old_phase = measure_ddmdt_phase();
        for _ in 0..1024 {
            hmc7043_sysref_slip();
            let phase = measure_ddmdt_phase();
            let step = (DDMTD_N + old_phase - phase) % DDMTD_N;
            if (step - expected_step).abs() > tolerance {
                error!("  ...got unexpected step: {} ({} -> {})", step, old_phase, phase);
                return Err("HMC7043 SYSREF slip produced unexpected DDMTD step");
            }
            old_phase = phase;
        }
        info!("  ...passed");
        Ok(())
    }

    fn sysref_sh_error() -> bool {
        unsafe {
            csr::sysref_sampler::sh_error_reset_write(1);
            clock::spin_us(1);
            csr::sysref_sampler::sh_error_reset_write(0);
            clock::spin_us(10);
            csr::sysref_sampler::sh_error_read() != 0
        }
    }

    const SYSREF_SH_PRECISION_SHIFT: i32 = 5;
    const SYSREF_SH_PRECISION: i32 = 1 << SYSREF_SH_PRECISION_SHIFT;
    const SYSREF_SH_MOD: i32 = 1 << (DDMTD_N_SHIFT + SYSREF_SH_PRECISION_SHIFT);

    #[derive(Default)]
    struct SysrefShLimits {
        rising_phases: [i32; SYSREF_SH_PRECISION as usize],
        falling_phases: [i32; SYSREF_SH_PRECISION as usize],
    }

    fn measure_sysref_sh_limits() -> Result<SysrefShLimits, &'static str> {
        let mut ret = SysrefShLimits::default();
        let mut nslips = 0;
        let mut rising_n = 0;
        let mut falling_n = 0;

        let mut previous = sysref_sh_error();
        while rising_n < SYSREF_SH_PRECISION || falling_n < SYSREF_SH_PRECISION {
            hmc7043_sysref_slip();
            nslips += 1;
            if nslips > 1024 {
                return Err("too many slips and not enough SYSREF S/H error transitions");
            }

            let current = sysref_sh_error();
            let phase = measure_ddmdt_phase();
            if current && !previous && rising_n < SYSREF_SH_PRECISION {
                ret.rising_phases[rising_n as usize] = phase << SYSREF_SH_PRECISION_SHIFT;
                rising_n += 1;
            }
            if !current && previous && falling_n < SYSREF_SH_PRECISION {
                ret.falling_phases[falling_n as usize] = phase << SYSREF_SH_PRECISION_SHIFT;
                falling_n += 1;
            }
            previous = current;
        }
        Ok(ret)
    }

    fn max_phase_deviation(average: i32, phases: &[i32]) -> i32 {
        let mut ret = 0;
        for phase in phases.iter() {
            let deviation = (phase - average + DDMTD_N) % DDMTD_N;
            if deviation > ret {
                ret = deviation;
            }
        }
        return ret;
    }

    fn reach_sysref_ddmtd_target(target: i32, tolerance: i32) -> Result<i32, &'static str> {
        for _ in 0..1024 {
            let delta = (measure_ddmdt_phase() - target + DDMTD_N) % DDMTD_N;
            if delta <= tolerance {
                return Ok(delta)
            }
            hmc7043_sysref_slip();
        }
        Err("failed to reach SYSREF DDMTD phase target")
    }

    fn calibrate_sysref_target(rising_average: i32, falling_average: i32) -> Result<i32, &'static str> {
        info!("calibrating SYSREF DDMTD target phase...");
        let coarse_target =
            if rising_average < falling_average {
                (rising_average + falling_average)/2
            } else {
                ((falling_average - (DDMTD_N - rising_average))/2 + DDMTD_N) % DDMTD_N
            };
        info!("  SYSREF calibration coarse target: {}", coarse_target);
        reach_sysref_ddmtd_target(coarse_target, 8)?;
        let target = measure_ddmdt_phase();
        info!("  ...done, target={}", target);
        Ok(target)
    }

    fn sysref_get_tsc_phase_raw() -> Result<u8, &'static str> {
        if sysref_sh_error() {
            return Err("SYSREF failed S/H timing");
        }
        let ret = unsafe { csr::sysref_sampler::sysref_phase_read() };
        Ok(ret)
    }

    // Note: the code below assumes RTIO/SYSREF frequency ratio is a power of 2

    fn sysref_get_tsc_phase() -> Result<i32, &'static str> {
        let mask = (SYSREF_DIV/FPGA_CLK_DIV - 1) as u8;
        Ok((sysref_get_tsc_phase_raw()? & mask) as i32)
    }

    pub fn test_sysref_frequency() -> Result<(), &'static str> {
        info!("testing SYSREF frequency against raw TSC phase bit toggles...");

        let mut all_toggles = 0;
        let initial_phase = sysref_get_tsc_phase_raw()?;
        for _ in 0..20000 {
            clock::spin_us(1);
            all_toggles |= sysref_get_tsc_phase_raw()? ^ initial_phase;
        }

        let ratio = (SYSREF_DIV/FPGA_CLK_DIV) as u8;
        let expected_toggles = 0xff ^ (ratio - 1);
        if all_toggles == expected_toggles {
            info!("  ...done (0x{:02x})", all_toggles);
            Ok(())
        } else {
            error!("  ...unexpected toggles: got 0x{:02x}, expected 0x{:02x}",
                all_toggles, expected_toggles);
            Err("unexpected toggles")
        }
    }

    fn sysref_slip_rtio_cycle()  {
        for _ in 0..FPGA_CLK_DIV {
            hmc7043_sysref_slip();
        }
    }

    pub fn test_slip_tsc() -> Result<(), &'static str> {
        info!("testing HMC7043 SYSREF slip against TSC phase...");
        let initial_phase = sysref_get_tsc_phase()?;
        let modulo = (SYSREF_DIV/FPGA_CLK_DIV) as i32;
        for i in 0..128 {
            sysref_slip_rtio_cycle();
            let expected_phase = (initial_phase + i + 1) % modulo;
            let phase = sysref_get_tsc_phase()?;
            if phase != expected_phase {
                error!("  ...unexpected TSC phase: got {}, expected {} ", phase, expected_phase);
                return Err("HMC7043 SYSREF slip produced unexpected TSC phase");
            }
        }
        info!("  ...done");
        Ok(())
    }

    pub fn sysref_rtio_align() -> Result<(), &'static str> {
        info!("aligning SYSREF with RTIO TSC...");
        let mut nslips = 0;
        loop {
            sysref_slip_rtio_cycle();
            if sysref_get_tsc_phase()? == 0 {
                info!("  ...done");
                return Ok(())
            }

            nslips += 1;
            if nslips > SYSREF_DIV/FPGA_CLK_DIV {
                return Err("failed to find SYSREF transition aligned with RTIO TSC");
            }
        }
    }

    pub fn sysref_auto_rtio_align() -> Result<(), &'static str> {
        init_ddmtd()?;
        test_ddmtd_stability(true, 4)?;
        test_ddmtd_stability(false, 1)?;
        test_slip_ddmtd()?;

        info!("determining SYSREF S/H limits...");
        let sysref_sh_limits = measure_sysref_sh_limits()?;
        let rising_average = average_phases(&sysref_sh_limits.rising_phases, SYSREF_SH_MOD);
        let falling_average = average_phases(&sysref_sh_limits.falling_phases, SYSREF_SH_MOD);
        let rising_max_deviation = max_phase_deviation(rising_average, &sysref_sh_limits.rising_phases);
        let falling_max_deviation = max_phase_deviation(falling_average, &sysref_sh_limits.falling_phases);

        let rising_average = rising_average >> SYSREF_SH_PRECISION_SHIFT;
        let falling_average = falling_average >> SYSREF_SH_PRECISION_SHIFT;
        let rising_max_deviation = rising_max_deviation >> SYSREF_SH_PRECISION_SHIFT;
        let falling_max_deviation = falling_max_deviation >> SYSREF_SH_PRECISION_SHIFT;

        info!("  SYSREF S/H average limits (DDMTD phases): {} {}", rising_average, falling_average);
        info!("  SYSREF S/H maximum limit deviation: {} {}", rising_max_deviation, falling_max_deviation);
        if rising_max_deviation > 8 || falling_max_deviation > 8 {
            return Err("excessive SYSREF S/H limit deviation");
        }
        info!("  ...done");

        let entry = config::read_str("sysref_ddmtd_phase_fpga", |r| r.map(|s| s.parse()));
        let target_phase = match entry {
            Ok(Ok(phase)) => {
                info!("using FPGA SYSREF DDMTD phase target from config: {}", phase);
                phase
            }
            _ => {
                let phase = calibrate_sysref_target(rising_average, falling_average)?;
                if let Err(e) = config::write_int("sysref_ddmtd_phase_fpga", phase as u32) {
                    error!("failed to update FPGA SYSREF DDMTD phase target in config: {}", e);
                }
                phase
            }
        };

        info!("aligning SYSREF with RTIO clock...");
        let delta = reach_sysref_ddmtd_target(target_phase, 3)?;
        if sysref_sh_error() {
            return Err("SYSREF does not meet S/H timing at DDMTD phase target");
        }
        info!("  ...done, delta={}", delta);

        test_sysref_frequency()?;
        test_slip_tsc()?;
        sysref_rtio_align()?;

        Ok(())
    }

    fn sysref_cal_dac(dacno: u8) -> Result<u8, &'static str> {
        info!("calibrating SYSREF delay at DAC-{}...", dacno);

        // Allocate for more than expected as jitter may create spurious entries.
        let mut limits_buf = [0; 8];
        let mut n_limits = 0;

        limits_buf[n_limits] = -1;
        n_limits += 1;

        // avoid spurious rotation at delay=0
        hmc7043_sysref_delay_dac(dacno, 0);
        ad9154_sync(dacno)?;

        for scan_delay in 0..HMC7043_ANALOG_DELAY_RANGE {
            hmc7043_sysref_delay_dac(dacno, scan_delay);
            if ad9154_sync(dacno)? {
                limits_buf[n_limits] = scan_delay as i16;
                n_limits += 1;
                if n_limits >= limits_buf.len() - 1  {
                    break;
                }
            }
        }

        limits_buf[n_limits] = HMC7043_ANALOG_DELAY_RANGE as i16;
        n_limits += 1;

        info!("  using limits: {:?}", &limits_buf[..n_limits]);

        let mut delay = 0;
        let mut best_margin = 0;

        for i in 0..(n_limits-1) {
            let margin = limits_buf[i+1] - limits_buf[i];
            if margin > best_margin {
                best_margin = margin;
                delay = ((limits_buf[i+1] + limits_buf[i])/2) as u8;
            }
        }

        info!("  ...done, delay={}", delay);
        Ok(delay)
    }

    fn sysref_dac_align(dacno: u8, delay: u8) -> Result<(), &'static str> {
        let tolerance = 5;

        info!("verifying SYSREF margins at DAC-{}...", dacno);

        // avoid spurious rotation at delay=0
        hmc7043_sysref_delay_dac(dacno, 0);
        ad9154_sync(dacno)?;

        let mut rotation_seen = false;
        for scan_delay in 0..HMC7043_ANALOG_DELAY_RANGE {
            hmc7043_sysref_delay_dac(dacno, scan_delay);
            if ad9154_sync(dacno)? {
                rotation_seen = true;
                let distance = (scan_delay as i16 - delay as i16).abs();
                if distance < tolerance {
                    error!("  rotation at delay={} is {} delay steps from target (FAIL)", scan_delay, distance);
                    return Err("insufficient SYSREF margin at DAC");
                } else {
                    info!("  rotation at delay={} is {} delay steps from target (PASS)", scan_delay, distance);
                }
            }
        }

        if !rotation_seen {
            return Err("no rotation seen when scanning DAC SYSREF delay");
        }

        info!("  ...done");

        // We tested that the value is correct - now use it
        hmc7043_sysref_delay_dac(dacno, delay);
        ad9154_sync(dacno)?;

        Ok(())
    }

    pub fn sysref_auto_dac_align() -> Result<(), &'static str> {
        // We assume that DAC SYSREF traces are length-matched so only one delay
        // value is needed, and we use DAC-0 as calibration reference.

        let entry = config::read_str("sysref_7043_delay_dac", |r| r.map(|s| s.parse()));
        let delay = match entry {
            Ok(Ok(delay)) => {
                info!("using DAC SYSREF delay from config: {}", delay);
                delay
            },
            _ => {
                let delay = sysref_cal_dac(0)?;
                if let Err(e) = config::write_int("sysref_7043_delay_dac", delay as u32) {
                    error!("failed to update DAC SYSREF delay in config: {}", e);
                }
                delay
            }
        };

        for dacno in 0..csr::JDCG.len() {
            sysref_dac_align(dacno as u8, delay)?;
        }
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
