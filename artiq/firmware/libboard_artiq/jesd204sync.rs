use board_misoc::{csr, clock, config};

use hmc830_7043::hmc7043;
use ad9154;

fn sysref_sh_error() -> bool {
    unsafe {
        csr::sysref_sampler::sh_error_reset_write(1);
        clock::spin_us(1);
        csr::sysref_sampler::sh_error_reset_write(0);
        clock::spin_us(10);
        csr::sysref_sampler::sh_error_read() != 0
    }
}

pub fn sysref_auto_rtio_align() -> Result<(), &'static str> {
    for _ in 0..256 {
        hmc7043::sysref_slip();
        let dt = unsafe { csr::sysref_ddmtd::dt_read() };
        let sh_error = sysref_sh_error();
        info!("dt={} sysref_sh_error={}", dt, sh_error);
    }
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
