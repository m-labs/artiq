use board_misoc::{csr, config};

use hmc830_7043::hmc7043;
use ad9154;

fn sysref_sample() -> bool {
    unsafe { csr::sysref_sampler::sample_result_read() == 1 }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum SysrefSample {
    Low,
    High,
    Unstable
}

fn sysref_sample_stable(phase_offset: u16) -> SysrefSample {
    hmc7043::sysref_offset_fpga(phase_offset);
    let s1 = sysref_sample();
    hmc7043::sysref_offset_fpga(phase_offset-5);
    let s2 = sysref_sample();
    if s1 == s2 {
        if s1 {
            return SysrefSample::High;
        } else {
            return SysrefSample::Low;
        }
    } else {
        return SysrefSample::Unstable;
    }
}

fn sysref_cal_fpga() -> Result<u16, &'static str> {
    info!("calibrating SYSREF phase offset at FPGA...");

    let initial_phase_offset = 136;

    let mut slips0 = 0;
    let mut slips1 = 0;
    // make sure we start in the 0 zone
    while sysref_sample_stable(initial_phase_offset) != SysrefSample::Low {
        hmc7043::sysref_slip();
        slips0 += 1;
        if slips0 > 1024 {
            return Err("failed to reach 1->0 transition (cal)");
        }
    }

    // get near the edge of the 0->1 transition
    while sysref_sample_stable(initial_phase_offset) != SysrefSample::High {
        hmc7043::sysref_slip();
        slips1 += 1;
        if slips1 > 1024 {
            return Err("failed to reach 0->1 transition (cal)");
        }
    }

    for d in 0..initial_phase_offset {
        let phase_offset = initial_phase_offset - d;
        hmc7043::sysref_offset_fpga(phase_offset);
        if !sysref_sample() {
            let result = phase_offset + 17;
            info!("  ...done, phase offset: {}", result);
            return Ok(result);
        }
    }
    return Err("failed to reach 1->0 transition with fine delay");
}

fn sysref_rtio_slip_to(target: bool) -> Result<u16, &'static str> {
    let mut slips = 0;
    while sysref_sample() != target {
        hmc7043::sysref_slip();
        slips += 1;
        if slips > 1024 {
            return Err("failed to reach SYSREF transition");
        }
    }
    Ok(slips)
}

fn sysref_rtio_check_period(phase_offset: u16) -> Result<(), &'static str> {
    const N: usize = 32;
    let mut nslips = [0; N];
    let mut error = false;

    // meet setup/hold (assuming FPGA timing margins are OK)
    hmc7043::sysref_offset_fpga(phase_offset);
    // if we are already in the 1 zone, get out of it
    sysref_rtio_slip_to(false)?;
    for i in 0..N {
        nslips[i] = sysref_rtio_slip_to(i % 2 == 0)?;
        if nslips[i] != hmc7043::SYSREF_DIV/2 {
            error = true;
        }
    }
    if error {
        info!("  SYSREF slip half-periods: {:?}", nslips);
        return Err("unexpected SYSREF slip half-periods seen");
    } else {
        info!("  SYSREF slip half-periods at FPGA have expected length ({})", hmc7043::SYSREF_DIV/2);
    }
    Ok(())
}

fn sysref_rtio_align(phase_offset: u16) -> Result<(), &'static str> {
    // This needs to take place before DAC SYSREF scan, as
    // the HMC7043 input clock (which defines slip resolution)
    // is 2x the DAC clock, so there are two possible phases from
    // the divider states. This deterministically selects one.

    info!("aligning SYSREF with RTIO...");

    sysref_rtio_check_period(phase_offset)?;

    // meet setup/hold (assuming FPGA timing margins are OK)
    hmc7043::sysref_offset_fpga(phase_offset);
    // if we are already in the 1 zone, get out of it
    let slips0 = sysref_rtio_slip_to(false)?;
    // get to the edge of the 0->1 transition (our final setpoint)
    let slips1 = sysref_rtio_slip_to(true)?;
    info!("  ...done ({}/{} slips)", slips0, slips1);

    let mut margin_minus = None;
    for d in 0..phase_offset {
        hmc7043::sysref_offset_fpga(phase_offset - d);
        if !sysref_sample() {
            margin_minus = Some(d);
            break;
        }
    }
    // meet setup/hold
    hmc7043::sysref_offset_fpga(phase_offset);

    if margin_minus.is_some() {
        let margin_minus = margin_minus.unwrap();
        // one phase slip (period of the 1.2GHz input clock)
        let period = 2*17; // approximate: 2 digital coarse delay steps
        let margin_plus = if period > margin_minus { period - margin_minus } else { 0 };
        info!("  margins at FPGA: -{} +{}", margin_minus, margin_plus);
        if margin_minus < 10 || margin_plus < 10 {
            return Err("SYSREF margin at FPGA is too small, board needs recalibration");
        }
    } else {
        return Err("unable to determine SYSREF margin at FPGA");
    }

    Ok(())
}

pub fn sysref_auto_rtio_align() -> Result<(), &'static str> {
    let entry = config::read_str("sysref_phase_fpga", |r| r.map(|s| s.parse()));
    let phase_offset = match entry {
        Ok(Ok(phase)) => phase,
        _ => {
            let phase = sysref_cal_fpga()?;
            if let Err(e) = config::write_int("sysref_phase_fpga", phase as u32) {
                error!("failed to update FPGA SYSREF phase in config: {}", e);
            }
            phase
        }
    };
    sysref_rtio_align(phase_offset)
}

fn sysref_cal_dac(dacno: u8) -> Result<u16, &'static str> {
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
        if d > 128 {
            return Err("no sync errors found when scanning delay");
        }
    }

    d += 17;  // get away from jitter
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
        if d > 128 {
            return Err("no sync errors found when scanning delay");
        }
    }

    let phase = (dmin+dmax)/2;
    info!("  ...done, min={}, max={}, result={}", dmin, dmax, phase);
    Ok(phase)
}

fn sysref_dac_align(dacno: u8, phase: u16) -> Result<(), &'static str> {
    let mut margin_minus = None;
    let mut margin_plus = None;

    info!("verifying SYSREF margins at DAC-{}...", dacno);

    hmc7043::sysref_offset_dac(dacno, phase);
    ad9154::dac_sync(dacno)?;
    for d in 0..128 {
        hmc7043::sysref_offset_dac(dacno, phase - d);
        let realign_occured = ad9154::dac_sync(dacno)?;
        if realign_occured {
            margin_minus = Some(d);
            break;
        }
    }

    hmc7043::sysref_offset_dac(dacno, phase);
    ad9154::dac_sync(dacno)?;
    for d in 0..128 {
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
        if margin_minus < 10 || margin_plus < 10 {
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

    let entry = config::read_str("sysref_phase_dac", |r| r.map(|s| s.parse()));
    let phase = match entry {
        Ok(Ok(phase)) => phase,
        _ => {
            let phase = sysref_cal_dac(0)?;
            if let Err(e) = config::write_int("sysref_phase_dac", phase as u32) {
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
