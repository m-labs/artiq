/*
 * HMC830 config:
 * 100MHz input, 1.2GHz output
 * fvco = (refclk / r_divider) * n_divider
 * fout = fvco/2
 *
 * HMC7043 config:
 * dac clock: 600MHz (div=1)
 * fpga clock: 150MHz (div=4)
 * sysref clock: 9.375MHz (div=64)
 */

mod clock_mux {
    use csr;

    const CLK_SRC_EXT_SEL : u8 = 1 << 0;
    const REF_CLK_SRC_SEL : u8 = 1 << 1;
    const DAC_CLK_SRC_SEL : u8 = 1 << 2;

    pub fn init() {
        unsafe {
            csr::clock_mux::out_write(
                1*CLK_SRC_EXT_SEL |  // use ext clk from sma
                1*REF_CLK_SRC_SEL |  //
                0*DAC_CLK_SRC_SEL);  // use clk from dac_clk // FIXME (should use hmc830 output)
        }
    }
}

mod hmc830 {
    use clock;
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
        (0x3, 0x30), // n_divider
    ];

    fn spi_setup() {
        unsafe {
            csr::converter_spi::offline_write(1);
            csr::converter_spi::cs_polarity_write(0b0001);
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
            csr::converter_spi::data_read_read() & 0xffffff
        }
    }

    pub fn init() -> Result<(), &'static str> {
        spi_setup();
        let id = read(0x00);
        if id != 0xa7975 {
            error!("invalid HMC830 ID: 0x{:08x}", id);
            return Err("invalid HMC830 identification");
        } else {
            info!("HMC830 found");
        }
        info!("HMC830 configuration...");
        for &(addr, data) in HMC830_WRITES.iter() {
            write(addr, data);
        }

        let t = clock::get_ms();
        info!("HMC830 waiting for lock...");
        while read(0x12) & 0x02 == 0 {
            if clock::get_ms() > t + 2000 {
                return Err("HMC830 lock timeout");
            }
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
            csr::converter_spi::cs_polarity_write(0b0001);
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
        let cmd = (1 << 15) | addr;
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
        } else {
            info!("HMC7043 found");
        }
        info!("HMC7043 configuration...");
        for &(addr, data) in HMC7043_WRITES.iter() {
            write(addr, data);
        }
        Ok(())
    }
}

pub fn init() -> Result<(), &'static str> {
    clock_mux::init();
    //hmc830::init()?; // FIXME
    hmc7043::init()
}
