use super::{csr, clock};

const CCLK_BIT: u8 = 1 << 0;
const DIN_BIT: u8 = 1 << 1;
const DONE_BIT: u8 = 1 << 2;
const INIT_B_BIT: u8 = 1 << 3;
const PROGRAM_B_BIT: u8 = 1 << 4;

unsafe fn shift_u8(data: u8) {
    for i in 0..8 {
        let mut bits: u8 = PROGRAM_B_BIT;
        if data & (0x80 >> i) != 0 {
            bits |= DIN_BIT;
        }
        // Without delays, this is about 6 MHz CCLK which is fine.
        csr::slave_fpga_cfg::out_write(bits);
        // clock::spin_us(1);
        csr::slave_fpga_cfg::out_write(bits | CCLK_BIT);
        // clock::spin_us(1);
    }
}

pub fn prepare() -> Result<(), &'static str> {
    unsafe {
        if csr::slave_fpga_cfg::in_read() & DONE_BIT != 0 {
            println!("  DONE before loading");
        }
        if csr::slave_fpga_cfg::in_read() & INIT_B_BIT == 0 {
            println!("  INIT asserted before loading");
        }

        csr::slave_fpga_cfg::out_write(0);
        csr::slave_fpga_cfg::oe_write(CCLK_BIT | DIN_BIT | PROGRAM_B_BIT);
        clock::spin_us(1_000);  // TPROGRAM=250ns min, be_generous
        if csr::slave_fpga_cfg::in_read() & INIT_B_BIT != 0 {
            return Err("Did not assert INIT in reaction to PROGRAM");
        }
        csr::slave_fpga_cfg::out_write(PROGRAM_B_BIT);
        clock::spin_us(10_000);  // TPL=5ms max
        if csr::slave_fpga_cfg::in_read() & INIT_B_BIT == 0 {
            return Err("Did not exit INIT after releasing PROGRAM");
        }
        if csr::slave_fpga_cfg::in_read() & DONE_BIT != 0 {
            return Err("DONE high despite PROGRAM");
        }
    }
    Ok(())
}

pub fn input(data: &[u8]) -> Result<(), &'static str> {
    unsafe {
        for i in data {
            shift_u8(*i);
            if csr::slave_fpga_cfg::in_read() & INIT_B_BIT == 0 {
                return Err("INIT asserted during load");
            }
        }
    }
    Ok(())
}

pub fn startup() -> Result<(), &'static str> {
    unsafe {
        let t = clock::get_ms();
        while csr::slave_fpga_cfg::in_read() & DONE_BIT == 0 {
            if clock::get_ms() > t + 100 {
                return Err("Timeout wating for DONE after loading");
            }
            shift_u8(0xff);
        }
        shift_u8(0xff);  // "Compensate for Special Startup Conditions"
        csr::slave_fpga_cfg::out_write(PROGRAM_B_BIT);
        csr::slave_fpga_cfg::oe_write(PROGRAM_B_BIT);
    }
    Ok(())
}
