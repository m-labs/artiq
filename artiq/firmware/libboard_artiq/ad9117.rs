use spi;
use board_misoc::{csr, clock};

const DATA_CTRL_REG : u8 = 0x02;
const IRCML_REG : u8 = 0x05;
const QRCML_REG : u8 = 0x08;
const CLKMODE_REG : u8 = 0x14;
const VERSION_REG : u8 = 0x1F;

const RETIMER_CLK_PHASE : u8 = 0b11;

fn hard_reset() {
    unsafe {
        // Min Pulse Width: 50ns
        csr::dac_rst::out_write(1);
        clock::spin_us(1);
        csr::dac_rst::out_write(0);
    }
}

fn spi_setup(dac_sel: u8, half_duplex: bool, end: bool) -> Result<(), &'static str> { 
    // Clear the cs_polarity and cs config
    spi::set_config(0, 0, 8, 64, 0b1111)?;
    spi::set_config(0, 1 << 3, 8, 64, (7 - dac_sel) << 1)?;
    spi::set_config(0, (half_duplex as u8) << 7 | (end as u8) << 1, 8, 64, 0b0001)?;
    Ok(())
}

fn write(dac_sel: u8, reg: u8, val: u8) -> Result<(), &'static str> {
    spi_setup(dac_sel, false, false)?;
    spi::write(0, (reg as u32) << 24)?;
    spi_setup(dac_sel, false, true)?;
    spi::write(0, (val as u32) << 24)?;
    
    Ok(())
}

fn read(dac_sel: u8, reg: u8) -> Result<u8, &'static str> {
    spi_setup(dac_sel, false, false)?;
    spi::write(0, ((reg | 1 << 7) as u32) << 24)?;
    spi_setup(dac_sel, true, true)?;
    spi::write(0, 0)?;

    Ok(spi::read(0)? as u8)
}

pub fn init() -> Result<(), &'static str> {
    hard_reset();
    
    for channel in 0..8 {
        let reg = read(channel, VERSION_REG)?;
        if reg != 0x0A {
            debug!("DAC AD9117 Channel {} has incorrect hardware version. VERSION reg: {:02x}", channel, reg);
            return Err("DAC AD9117 hardware version is not equal to 0x0A");
        }
        // Check for the presence of DCLKIO and CLKIN
        let reg = read(channel, CLKMODE_REG)?;
        if reg >> 4 & 1 != 0 {
            debug!("DAC AD9117 Channel {} retiming fails. CLKMODE reg: {:02x}", channel, reg);
            return Err("DAC AD9117 retiming failure");
        }

        // Force RETIMER-CLK to be Phase 1 as DCLKIO and CLKIN is known to be safe at Phase 1
        // See Issue #2200
        write(channel, CLKMODE_REG, RETIMER_CLK_PHASE << 6 | 1 << 2 | RETIMER_CLK_PHASE)?;

        // Set the DACs input data format to be twos complement
        // Set IFIRST and IRISING to True
        write(channel, DATA_CTRL_REG, 1 << 7 | 1 << 5 | 1 << 4)?;

        // Enable internal common mode resistors of both channels
        write(channel, IRCML_REG, 1 << 7)?;
        write(channel, QRCML_REG, 1 << 7)?;
    }
    
    Ok(())
}
