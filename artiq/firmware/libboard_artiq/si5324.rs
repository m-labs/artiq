use core::result;
use board_misoc::clock;
#[cfg(not(si5324_soft_reset))]
use board_misoc::csr;
use i2c;

type Result<T> = result::Result<T, &'static str>;

const BUSNO: u8 = 0;
const ADDRESS: u8 = 0x68;

#[cfg(any(soc_platform = "kasli",
          soc_platform = "sayma_amc",
          soc_platform = "kc705"))]
fn pca9548_select(address: u8, channels: u8) -> Result<()> {
    i2c::start(BUSNO).unwrap();
    if !i2c::write(BUSNO, address << 1).unwrap() {
        return Err("PCA9548 failed to ack write address")
    }
    if !i2c::write(BUSNO, channels).unwrap() {
        return Err("PCA9548 failed to ack control word")
    }
    i2c::stop(BUSNO).unwrap();
    Ok(())
}

#[cfg(not(si5324_soft_reset))]
fn hard_reset() {
    unsafe { csr::si5324_rst_n::out_write(0); }
    clock::spin_us(1_000);
    unsafe { csr::si5324_rst_n::out_write(1); }
    clock::spin_us(10_000);
}

// NOTE: the logical parameters DO NOT MAP to physical values written
// into registers. They have to be mapped; see the datasheet.
// DSPLLsim reports the logical parameters in the design summary, not
// the physical register values.
pub struct FrequencySettings {
    pub n1_hs: u8,
    pub nc1_ls: u32,
    pub n2_hs: u8,
    pub n2_ls: u32,
    pub n31: u32,
    pub n32: u32,
    pub bwsel: u8,
    pub crystal_ref: bool
}

pub enum Input {
    Ckin1,
    Ckin2,
}

fn map_frequency_settings(settings: &FrequencySettings) -> Result<FrequencySettings> {
    if settings.nc1_ls != 0 && (settings.nc1_ls % 2) == 1 {
        return Err("NC1_LS must be 0 or even")
    }
    if settings.nc1_ls > (1 << 20) {
        return Err("NC1_LS is too high")
    }
    if (settings.n2_ls % 2) == 1 {
        return Err("N2_LS must be even")
    }
    if settings.n2_ls > (1 << 20) {
        return Err("N2_LS is too high")
    }
    if settings.n31 > (1 << 19) {
        return Err("N31 is too high")
    }
    if settings.n32 > (1 << 19) {
        return Err("N32 is too high")
    }
    let r = FrequencySettings {
        n1_hs: match settings.n1_hs {
            4  => 0b000,
            5  => 0b001,
            6  => 0b010,
            7  => 0b011,
            8  => 0b100,
            9  => 0b101,
            10 => 0b110,
            11 => 0b111,
            _  => return Err("N1_HS has an invalid value")
        },
        nc1_ls: settings.nc1_ls - 1,
        n2_hs: match settings.n2_hs {
            4  => 0b000,
            5  => 0b001,
            6  => 0b010,
            7  => 0b011,
            8  => 0b100,
            9  => 0b101,
            10 => 0b110,
            11 => 0b111,
            _  => return Err("N2_HS has an invalid value")
        },
        n2_ls: settings.n2_ls - 1,
        n31: settings.n31 - 1,
        n32: settings.n32 - 1,
        bwsel: settings.bwsel,
        crystal_ref: settings.crystal_ref
    };
    Ok(r)
}

fn write(reg: u8, val: u8) -> Result<()> {
    i2c::start(BUSNO).unwrap();
    if !i2c::write(BUSNO, ADDRESS << 1).unwrap() {
        return Err("Si5324 failed to ack write address")
    }
    if !i2c::write(BUSNO, reg).unwrap() {
        return Err("Si5324 failed to ack register")
    }
    if !i2c::write(BUSNO, val).unwrap() {
        return Err("Si5324 failed to ack value")
    }
    i2c::stop(BUSNO).unwrap();
    Ok(())
}

#[cfg(si5324_soft_reset)]
fn write_no_ack_value(reg: u8, val: u8) -> Result<()> {
    i2c::start(BUSNO).unwrap();
    if !i2c::write(BUSNO, ADDRESS << 1).unwrap() {
        return Err("Si5324 failed to ack write address")
    }
    if !i2c::write(BUSNO, reg).unwrap() {
        return Err("Si5324 failed to ack register")
    }
    i2c::write(BUSNO, val).unwrap();
    i2c::stop(BUSNO).unwrap();
    Ok(())
}

fn read(reg: u8) -> Result<u8> {
    i2c::start(BUSNO).unwrap();
    if !i2c::write(BUSNO, ADDRESS << 1).unwrap() {
        return Err("Si5324 failed to ack write address")
    }
    if !i2c::write(BUSNO, reg).unwrap() {
        return Err("Si5324 failed to ack register")
    }
    i2c::restart(BUSNO).unwrap();
    if !i2c::write(BUSNO, (ADDRESS << 1) | 1).unwrap() {
        return Err("Si5324 failed to ack read address")
    }
    let val = i2c::read(BUSNO, false).unwrap();
    i2c::stop(BUSNO).unwrap();
    Ok(val)
}

fn ident() -> Result<u16> {
    Ok(((read(134)? as u16) << 8) | (read(135)? as u16))
}

#[cfg(si5324_soft_reset)]
fn soft_reset() -> Result<()> {
    write_no_ack_value(136, read(136)? | 0x80)?;
    clock::spin_us(10_000);
    Ok(())
}

fn has_xtal() -> Result<bool> {
    Ok((read(129)? & 0x01) == 0)  // LOSX_INT=0
}

fn has_ckin(input: Input) -> Result<bool> {
    match input {
        Input::Ckin1 => Ok((read(129)? & 0x02) == 0),  // LOS1_INT=0
        Input::Ckin2 => Ok((read(129)? & 0x04) == 0),  // LOS2_INT=0
    }
}

fn locked() -> Result<bool> {
    Ok((read(130)? & 0x01) == 0)  // LOL_INT=0
}

fn monitor_lock() -> Result<()> {
    info!("waiting for Si5324 lock...");
    let t = clock::get_ms();
    while !locked()? {
        // Yes, lock can be really slow.
        if clock::get_ms() > t + 20000 {
            return Err("Si5324 lock timeout");
        }
    }
    info!("  ...locked");
    Ok(())
}

pub fn setup(settings: &FrequencySettings, input: Input) -> Result<()> {
    let s = map_frequency_settings(settings)?;

    #[cfg(not(si5324_soft_reset))]
    hard_reset();

    #[cfg(soc_platform = "kasli")]
    {
        pca9548_select(0x70, 0)?;
        pca9548_select(0x71, 1 << 3)?;
    }
    #[cfg(soc_platform = "sayma_amc")]
    pca9548_select(0x70, 1 << 4)?;
    #[cfg(soc_platform = "kc705")]
    pca9548_select(0x74, 1 << 7)?;

    if ident()? != 0x0182 {
        return Err("Si5324 does not have expected product number");
    }

    #[cfg(si5324_soft_reset)]
    soft_reset()?;

    let cksel_reg = match input {
        Input::Ckin1 => 0b00,
        Input::Ckin2 => 0b01,
    };
    if settings.crystal_ref {
        write(0,   read(0)? | 0x40)?;                     // FREE_RUN=1
    }
    write(2,   (read(2)? & 0x0f) | (s.bwsel << 4))?;
    write(21,  read(21)? & 0xfe)?;                        // CKSEL_PIN=0
    write(3,   (read(3)? & 0x3f) | (cksel_reg << 6) | 0x10)?;  // CKSEL_REG, SQ_ICAL=1
    write(4,   (read(4)? & 0x3f) | (0b00 << 6))?;         // AUTOSEL_REG=b00
    write(6,   (read(6)? & 0xc0) | 0b111111)?;            // SFOUT2_REG=b111 SFOUT1_REG=b111
    write(25,  (s.n1_hs  << 5 ) as u8)?;
    write(31,  (s.nc1_ls >> 16) as u8)?;
    write(32,  (s.nc1_ls >> 8 ) as u8)?;
    write(33,  (s.nc1_ls)       as u8)?;
    write(34,  (s.nc1_ls >> 16) as u8)?;                  // write to NC2_LS as well
    write(35,  (s.nc1_ls >> 8 ) as u8)?;
    write(36,  (s.nc1_ls)       as u8)?;
    write(40,  (s.n2_hs  << 5 ) as u8 | (s.n2_ls  >> 16) as u8)?;
    write(41,  (s.n2_ls  >> 8 ) as u8)?;
    write(42,  (s.n2_ls)        as u8)?;
    write(43,  (s.n31    >> 16) as u8)?;
    write(44,  (s.n31    >> 8)  as u8)?;
    write(45,  (s.n31)          as u8)?;
    write(46,  (s.n32    >> 16) as u8)?;
    write(47,  (s.n32    >> 8)  as u8)?;
    write(48,  (s.n32)          as u8)?;
    write(137, read(137)? | 0x01)?;                       // FASTLOCK=1
    write(136, read(136)? | 0x40)?;                       // ICAL=1

    if !has_xtal()? {
        return Err("Si5324 misses XA/XB signal");
    }
    if !has_ckin(input)? {
        return Err("Si5324 misses clock input signal");
    }

    monitor_lock()?;
    Ok(())
}

pub fn select_input(input: Input) -> Result<()> {
    let cksel_reg = match input {
        Input::Ckin1 => 0b00,
        Input::Ckin2 => 0b01,
    };
    write(3,   (read(3)? & 0x3f) | (cksel_reg << 6))?;
    if !has_ckin(input)? {
        return Err("Si5324 misses clock input signal");
    }
    monitor_lock()?;
    Ok(())
}

#[cfg(has_siphaser)]
pub mod siphaser {
    use super::*;
    use board_misoc::{csr, clock};

    pub fn select_recovered_clock(rc: bool) -> Result<()> {
        write(3,   (read(3)? & 0xdf) | (1 << 5))?;  // DHOLD=1
        unsafe {
            csr::siphaser::switch_clocks_write(if rc { 1 } else { 0 });
        }
        write(3,   (read(3)? & 0xdf) | (0 << 5))?;  // DHOLD=0
        monitor_lock()?;
        Ok(())
    }

    fn phase_shift(direction: u8) {
        unsafe {
            csr::siphaser::phase_shift_write(direction);
            while csr::siphaser::phase_shift_done_read() == 0 {}
        }
        // wait for the Si5324 loop to stabilize
        clock::spin_us(500);
    }

    fn get_phaser_sample() -> bool {
        let mut sample = true;
        for _ in 0..32 {
            if unsafe { csr::siphaser::sample_result_read() } == 0 {
                sample = false;
            }
        }
        sample
    }

    const PS_MARGIN: u32 = 28;

    fn get_stable_phaser_sample() -> (bool, u32) {
        let mut nshifts: u32 = 0;
        loop {
            let s1 = get_phaser_sample();
            for _ in 0..PS_MARGIN {
                phase_shift(1);
            }
            let s2 = get_phaser_sample();
            for _ in 0..PS_MARGIN {
                phase_shift(1);
            }
            let s3 = get_phaser_sample();
            nshifts += 2*PS_MARGIN;
            if s1 == s2 && s2 == s3 {
                for _ in 0..PS_MARGIN {
                    phase_shift(0);
                }
                nshifts -= PS_MARGIN;
                return (s2, nshifts);
            }
        }
    }

    pub fn calibrate_skew(skew: u16) -> Result<()> {
        // Get into a 0 region
        let (s1, mut nshifts) = get_stable_phaser_sample();
        if s1 {
            while get_phaser_sample() {
                phase_shift(1);
                nshifts += 1;
            }
            for _ in 0..PS_MARGIN {
                phase_shift(1);
            }
            nshifts += PS_MARGIN;
        }

        // Get to the 0->1 transition
        while !get_phaser_sample() {
            phase_shift(1);
            nshifts += 1;
        }
        info!("nshifts to 0->1 siphaser transition: {} ({}deg)", nshifts, nshifts*360/(56*8));

        // Apply specified skew referenced to that transition
        for _ in 0..skew {
            phase_shift(1);
        }
        Ok(())
    }
}
