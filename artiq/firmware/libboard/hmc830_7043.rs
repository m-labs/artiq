/*
 * HMC830 config:
 * 100MHz input, 1GHz output
 * fvco = (refclk / r_divider) * n_divider
 * fout = fvco/2
 *
 * HMC7043 config:
 * dac clock: 1GHz (div=1)
 * fpga clock: 250MHz (div=4)
 * sysref clock: 15.625MHz (div=64)
 */

mod hmc830 {
    use csr;

    const HMC830_WRITES: [(u8, u32); 16] = [
        (0x0, 0x20),
        (0x1, 0x2),
        (0x2, 0x2), // r_divider
        (0x5, 0x1628),
        (0x5, 0x60a0),
        (0x5, 0xe110),
        (0x5, 0x2818),
        (0x5, 0x0),
        (0x6, 0x303ca),
        (0x7, 0x14d),
        (0x8, 0xc1beff),
        (0x9, 0x153fff),
        (0xa, 0x2046),
        (0xb, 0x7c061),
        (0xf, 0x81),
        (0x3, 0x28), // n_divider
    ];

    fn spi_setup() {
        unsafe {
            csr::converter_spi::offline_write(1);
            csr::converter_spi::cs_polarity_write(0);
            csr::converter_spi::clk_polarity_write(0);
            csr::converter_spi::clk_phase_write(0);
            csr::converter_spi::lsb_first_write(0);
            csr::converter_spi::half_duplex_write(0);
            csr::converter_spi::clk_div_write_write(8);
            csr::converter_spi::clk_div_read_write(8);
            csr::converter_spi::cs_write(1 << csr::CONFIG_CONVERTER_SPI_HMC830_CS);
            csr::converter_spi::offline_write(0);
        }
    }

    fn write(addr: u8, data: u32) {
        let cmd = (0 << 6) | addr;
        let val = ((cmd as u32) << 24) | data;
        unsafe {
            csr::converter_spi::xfer_len_write_write(32);
            csr::converter_spi::xfer_len_read_write(0);
            csr::converter_spi::data_write_write(val << (32-31));
            while csr::converter_spi::pending_read() != 0 {}
            while csr::converter_spi::active_read() != 0 {}
        }
    }

    fn read(addr: u8) -> u32 {
        let cmd = (1 << 6) | addr;
        let val = (cmd as u32) << 24;
        unsafe {
            csr::converter_spi::xfer_len_write_write(7);
            csr::converter_spi::xfer_len_read_write(25);
            csr::converter_spi::data_write_write(val << (32-31));
            while csr::converter_spi::pending_read() != 0 {}
            while csr::converter_spi::active_read() != 0 {}
            csr::converter_spi::data_read_read()
        }
    }

    pub fn init() -> Result<(), &'static str> {
        spi_setup();
        let id = read(0);
        if id != 0xa7975 {
            error!("invalid HMC830 ID: 0x{:08x}", id);
            return Err("invalid HMC830 identification");
        }
        for &(addr, data) in HMC830_WRITES.iter() {
            write(addr, data);
        }
        Ok(())
    }
}

mod hmc7043 {
    use csr;

    include!(concat!(env!("OUT_DIR"), "/hmc7043_writes.rs"));

    fn spi_setup() {
        unsafe {
            csr::converter_spi::offline_write(1);
            csr::converter_spi::cs_polarity_write(0);
            csr::converter_spi::clk_polarity_write(0);
            csr::converter_spi::clk_phase_write(0);
            csr::converter_spi::lsb_first_write(0);
            csr::converter_spi::half_duplex_write(1);
            csr::converter_spi::clk_div_write_write(8);
            csr::converter_spi::clk_div_read_write(8);
            csr::converter_spi::cs_write(1 << csr::CONFIG_CONVERTER_SPI_HMC7043_CS);
            csr::converter_spi::offline_write(0);
        }
    }

    fn write(addr: u16, data: u8) {
        let cmd = (0 << 15) | addr;
        let val = ((cmd as u32) << 8) | data as u32;
        unsafe {
            csr::converter_spi::xfer_len_write_write(24);
            csr::converter_spi::xfer_len_read_write(0);
            csr::converter_spi::data_write_write(val << (32-24));
            while csr::converter_spi::pending_read() != 0 {}
            while csr::converter_spi::active_read() != 0 {}
        }
    }

    fn read(addr: u16) -> u8 {
        let cmd = (0 << 15) | addr;
        let val = (cmd as u32) << 8;
        unsafe {
            csr::converter_spi::xfer_len_write_write(16);
            csr::converter_spi::xfer_len_read_write(8);
            csr::converter_spi::data_write_write(val << (32-24));
            while csr::converter_spi::pending_read() != 0 {}
            while csr::converter_spi::active_read() != 0 {}
            csr::converter_spi::data_read_read() as u8
        }
    }

    pub fn init() -> Result<(), &'static str> {
        spi_setup();
        let id = (read(0x78) as u32) << 16 | (read(0x79) as u32) << 8 | read(0x7a) as u32;
        if id != 0xf17904 {
            error!("invalid HMC7043 ID: 0x{:08x}", id);
            return Err("invalid HMC7043 identification");
        }
        for &(addr, data) in HMC7043_WRITES.iter() {
            write(addr, data);
        }
        Ok(())
    }
}

pub fn init() -> Result<(), &'static str> {
    hmc830::init()?;
    hmc7043::init()
}
