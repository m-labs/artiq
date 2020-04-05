pub const INIT: u8              = 0x00;
pub const PRINT_STATUS: u8      = 0x01;
pub const PRBS: u8              = 0x02;
pub const STPL: u8              = 0x03;

pub const SYSREF_DELAY_DAC: u8  = 0x10;
pub const SYSREF_SLIP: u8       = 0x11;
pub const SYNC: u8              = 0x12;

pub const DDMTD_SYSREF_RAW: u8  = 0x20;
pub const DDMTD_SYSREF: u8      = 0x21;


fn average_2phases(a: i32, b: i32, modulo: i32) -> i32 {
    let diff = ((a - b + modulo/2 + modulo) % modulo) - modulo/2;
    return (modulo + b + diff/2) % modulo;
}

pub fn average_phases(phases: &[i32], modulo: i32) -> i32 {
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

pub const RAW_DDMTD_N_SHIFT: i32 = 6;
pub const RAW_DDMTD_N: i32 = 1 << RAW_DDMTD_N_SHIFT;
pub const DDMTD_DITHER_BITS: i32 = 1;
pub const DDMTD_N_SHIFT: i32 = RAW_DDMTD_N_SHIFT + DDMTD_DITHER_BITS;
pub const DDMTD_N: i32 = 1 << DDMTD_N_SHIFT;

#[cfg(has_ad9154)]
use board_misoc::{clock, csr};

#[cfg(has_ad9154)]
pub fn init_ddmtd() -> Result<(), &'static str> {
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

#[cfg(has_ad9154)]
pub fn measure_ddmdt_phase_raw() -> i32 {
    unsafe { csr::sysref_ddmtd::dt_read() as i32 }
}

#[cfg(has_ad9154)]
pub fn measure_ddmdt_phase() -> i32 {
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
