use board_misoc::{csr, clock, config};

use hmc830_7043::hmc7043;
use ad9154;

fn average_2phases(a: i32, b:i32, modulo: i32) -> i32 {
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

const DDMTD_N_SHIFT: i32 = 6;
const DDMTD_N: i32 = 1 << DDMTD_N_SHIFT;

const SYSREF_SH_PRECISION_SHIFT: i32 = 5;
const SYSREF_SH_PRECISION: i32 = 1 << SYSREF_SH_PRECISION_SHIFT;
const SYSREF_SH_MOD: i32 = 1 << (DDMTD_N_SHIFT + SYSREF_SH_PRECISION_SHIFT);


fn measure_ddmdt_phase_raw() -> i32 {
    unsafe { csr::sysref_ddmtd::dt_read() as i32 }
}

fn measure_ddmdt_phase() -> i32 {
    let mut measurements = [0; SYSREF_SH_PRECISION as usize];
    for i in 0..SYSREF_SH_PRECISION {
        measurements[i as usize] = measure_ddmdt_phase_raw() << SYSREF_SH_PRECISION_SHIFT;
        clock::spin_us(10);
    }
    average_phases(&measurements, SYSREF_SH_MOD) >> SYSREF_SH_PRECISION_SHIFT
}

fn test_slip_ddmtd() -> Result<(), &'static str> {
    // expected_step = (RTIO clock frequency)*(DDMTD N)/(HMC7043 CLKIN frequency)
    let expected_step = 4;
    let tolerance = 1;

    info!("testing HMC7043 SYSREF slip against DDMTD...");
    let mut old_phase = measure_ddmdt_phase();
    for _ in 0..1024 {
        hmc7043::sysref_slip();
        let phase = measure_ddmdt_phase();
        let step = (DDMTD_N + old_phase - phase) % DDMTD_N;
        if (step - expected_step).abs() > tolerance {
            error!("  ...got unexpected step: {}", step);
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
        hmc7043::sysref_slip();
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
        let deviation = (phase - average).abs();
        if deviation > ret {
            ret = deviation;
        }
    }
    return ret;
}

fn reach_sysref_ddmtd_target(target: i32, tolerance: i32) -> Result<(), &'static str> {
    let mut phase = measure_ddmdt_phase();
    let mut nslips = 0;
    while (phase - target).abs() > tolerance {
        hmc7043::sysref_slip();
        nslips += 1;
        if nslips > 1024 {
            return Err("failed to reach SYSREF DDMTD phase target");
        }
        phase = measure_ddmdt_phase();
    }
    Ok(())
}

fn calibrate_sysref_target(rising_average: i32, falling_average: i32) -> Result<i32, &'static str> {
    let coarse_target = (falling_average - 16 + DDMTD_N) % DDMTD_N;  // HACK
    info!("SYSREF calibration coarse target: {}", coarse_target);
    reach_sysref_ddmtd_target(coarse_target, 2)?;
    let target = measure_ddmdt_phase();
    info!("SYSREF calibrated target: {}", target);
    Ok(target)
}

fn sysref_get_sample() -> Result<bool, &'static str> {
    if sysref_sh_error() {
        return Err("SYSREF failed S/H timing");
    }
    let ret = unsafe { csr::sysref_sampler::sample_result_read() } != 0;
    Ok(ret)
}

fn sysref_slip_rtio_cycle()  {
    for _ in 0..hmc7043::FPGA_CLK_DIV {
        hmc7043::sysref_slip();
    }
}

pub fn sysref_rtio_align() -> Result<(), &'static str> {
    let mut previous_sample = sysref_get_sample()?;
    let mut nslips = 0;
    loop {
        sysref_slip_rtio_cycle();
        let sample = sysref_get_sample()?;
        if sample && !previous_sample {
            info!("SYSREF aligned with RTIO TSC");
            return Ok(())
        }
        previous_sample = sample;

        nslips += 1;
        if nslips > hmc7043::SYSREF_DIV/hmc7043::FPGA_CLK_DIV {
            return Err("failed to find SYSREF transition aligned with RTIO TSC");
        }
    }
}

pub fn sysref_auto_rtio_align() -> Result<(), &'static str> {
    test_slip_ddmtd()?;

    let sysref_sh_limits = measure_sysref_sh_limits()?;
    let rising_average = average_phases(&sysref_sh_limits.rising_phases, SYSREF_SH_MOD);
    let falling_average = average_phases(&sysref_sh_limits.falling_phases, SYSREF_SH_MOD);
    let rising_max_deviation = max_phase_deviation(rising_average, &sysref_sh_limits.rising_phases);
    let falling_max_deviation = max_phase_deviation(falling_average, &sysref_sh_limits.falling_phases);

    let rising_average = rising_average >> SYSREF_SH_PRECISION_SHIFT;
    let falling_average = falling_average >> SYSREF_SH_PRECISION_SHIFT;
    let rising_max_deviation = rising_max_deviation >> SYSREF_SH_PRECISION_SHIFT;
    let falling_max_deviation = falling_max_deviation >> SYSREF_SH_PRECISION_SHIFT;

    info!("SYSREF S/H average limits (DDMTD phases): {} {}", rising_average, falling_average);
    info!("SYSREF S/H maximum limit deviation: {} {}", rising_max_deviation, falling_max_deviation);
    if rising_max_deviation > 4 || falling_max_deviation > 4 {
        return Err("excessive SYSREF S/H limit deviation");
    }

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

    reach_sysref_ddmtd_target(target_phase, 1)?;
    if sysref_sh_error() {
        return Err("SYSREF does not meet S/H timing at DDMTD phase target");
    }

    sysref_rtio_align()?;

    Ok(())
}

fn sysref_cal_dac(dacno: u8) -> Result<u8, &'static str> {
    info!("calibrating SYSREF phase at DAC-{}...", dacno);

    let mut d = 0;
    let dmin;
    let dmax;

    hmc7043::sysref_offset_dac(dacno, d);
    ad9154::dac_sync(dacno)?;

    loop {
        hmc7043::sysref_offset_dac(dacno, d);
        let realign_occured = ad9154::dac_sync(dacno)?;
        if realign_occured {
            dmin = d;
            break;
        }

        d += 1;
        if d > 23 {
            return Err("no sync errors found when scanning delay");
        }
    }

    d += 5;  // get away from jitter
    hmc7043::sysref_offset_dac(dacno, d);
    ad9154::dac_sync(dacno)?;

    loop {
        hmc7043::sysref_offset_dac(dacno, d);
        let realign_occured = ad9154::dac_sync(dacno)?;
        if realign_occured {
            dmax = d;
            break;
        }

        d += 1;
        if d > 23 {
            return Err("no sync errors found when scanning delay");
        }
    }

    let phase = (dmin+dmax)/2;
    info!("  ...done, min={}, max={}, result={}", dmin, dmax, phase);
    Ok(phase)
}

fn sysref_dac_align(dacno: u8, phase: u8) -> Result<(), &'static str> {
    let mut margin_minus = None;
    let mut margin_plus = None;

    info!("verifying SYSREF margins at DAC-{}...", dacno);

    hmc7043::sysref_offset_dac(dacno, phase);
    ad9154::dac_sync(dacno)?;
    for d in 0..24 {
        hmc7043::sysref_offset_dac(dacno, phase - d);
        let realign_occured = ad9154::dac_sync(dacno)?;
        if realign_occured {
            margin_minus = Some(d);
            break;
        }
    }

    hmc7043::sysref_offset_dac(dacno, phase);
    ad9154::dac_sync(dacno)?;
    for d in 0..24 {
        hmc7043::sysref_offset_dac(dacno, phase + d);
        let realign_occured = ad9154::dac_sync(dacno)?;
        if realign_occured {
            margin_plus = Some(d);
            break;
        }
    }

    if margin_minus.is_some() && margin_plus.is_some() {
        let margin_minus = margin_minus.unwrap();
        let margin_plus = margin_plus.unwrap();
        info!("  margins: -{} +{}", margin_minus, margin_plus);
        if margin_minus < 5 || margin_plus < 5 {
            return Err("SYSREF margins at DAC are too small, board needs recalibration");
        }
    } else {
        return Err("Unable to determine SYSREF margins at DAC");
    }

    // Put SYSREF at the correct phase and sync DAC
    hmc7043::sysref_offset_dac(dacno, phase);
    ad9154::dac_sync(dacno)?;

    Ok(())
}

pub fn sysref_auto_dac_align() -> Result<(), &'static str> {
    // We assume that DAC SYSREF traces are length-matched so only one phase
    // value is needed, and we use DAC-0 as calibration reference.

    let entry = config::read_str("sysref_7043_phase_dac", |r| r.map(|s| s.parse()));
    let phase = match entry {
        Ok(Ok(phase)) => {
            info!("using DAC SYSREF phase from config: {}", phase);
            phase
        },
        _ => {
            let phase = sysref_cal_dac(0)?;
            if let Err(e) = config::write_int("sysref_7043_phase_dac", phase as u32) {
                error!("failed to update DAC SYSREF phase in config: {}", e);
            }
            phase
        }
    };

    for dacno in 0..csr::AD9154.len() {
        sysref_dac_align(dacno as u8, phase)?;
    }
    Ok(())
}
