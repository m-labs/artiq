/*
 * HMC830 config:
 * 100MHz input, 1.2GHz output
 * fvco = (refclk / r_divider) * n_divider
 * fout = fvco/2
 *
 * HMC7043 config:
 * dac clock: 600MHz (div=2)
 * fpga clock: 150MHz (div=8)
 * sysref clock: 9.375MHz (div=128)
 */

mod clock_mux {
    use board::csr;

    const CLK_SRC_EXT_SEL : u8 = 1 << 0;
    const REF_CLK_SRC_SEL : u8 = 1 << 1;
    const DAC_CLK_SRC_SEL : u8 = 1 << 2;

    pub fn init() {
        unsafe {
            csr::clock_mux::out_write(
                1*CLK_SRC_EXT_SEL |  // use ext clk from sma
                1*REF_CLK_SRC_SEL |
                1*DAC_CLK_SRC_SEL);
        }
    }
}

mod hmc830 {
    use board::{csr, clock};

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
        info!("waiting for lock...");
        while read(0x12) & 0x02 == 0 {
            if clock::get_ms() > t + 2000 {
                error!("HMC830 lock timeout. Register dump:");
                for addr in 0x00..0x14 {
                    // These registers don't exist (in the data sheet at least)
                    if addr == 0x0d || addr == 0x0e { continue; }
                    error!("[0x{:02x}] = 0x{:04x}", addr, read(addr));
                }
            //    return Err("HMC830 lock timeout");
                break;
            }
        }

        Ok(())
    }
}

mod hmc7043 {
    use board::csr;
    
    // To do: check which output channels we actually need
    const DAC_CLK_DIV: u32 = 2;
    const FPGA_CLK_DIV: u32 = 8;
    const SYSREF_DIV: u32 = 128;

    // enabled, divider, analog phase shift, digital phase shift
    const OUTPUT_CONFIG: [(bool, u32, u8, u8); 14] = [
        (true, DAC_CLK_DIV, 0x0, 0x0),  // 0: DAC2_CLK
        (true, SYSREF_DIV, 0x0, 0x0),   // 1: DAC2_SYSREF
        (true, DAC_CLK_DIV, 0x0, 0x0),  // 2: DAC1_CLK
        (true, SYSREF_DIV, 0x0, 0x0),   // 3: DAC1_SYSREF
        (false, 0, 0x0, 0x0),           // 4: ADC2_CLK
        (false, 0, 0x0, 0x0),           // 5: ADC2_SYSREF
        (true, FPGA_CLK_DIV, 0x0, 0x0), // 6: GTP_CLK2
        (true, SYSREF_DIV, 0x0, 0x0),   // 7: FPGA_DAC_SYSREF
        (true, FPGA_CLK_DIV, 0x0, 0x0), // 8: GTP_CLK1
        (true, FPGA_CLK_DIV, 0x0, 0x0), // 9: AMC_MASTER_AUX_CLK
        (true, FPGA_CLK_DIV, 0x0, 0x0), // 10: RTM_MASTER_AUX_CLK
        (false, 0, 0x0, 0x0),           // 11: FPGA_ADC_SYSREF
        (false, 0, 0x0, 0x0),           // 12: ADC1_CLK
        (false, 0, 0x0, 0x0),           // 13: ADC1_SYSREF
        ];


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

        write(0x0, 0x1);   // Software reset
        write(0x0, 0x0);

        write(0x1, 0x40);  // Enable high-performace/low-noise mode
        write(0x3, 0x10);  // Disable SYSREF timer
        write(0xA, 0x06);  // Disable the REFSYNCIN input
        write(0xB, 0x07);  // Enable the CLKIN input as LVPECL
        write(0x50, 0x1f); // Disable GPO pin
        write(0x9F, 0x4d); // Unexplained high-performance mode
        write(0xA0, 0xdf); // Unexplained high-performance mode

        // Enable required output groups
        write(0x4, (1 << 0) |
                   (1 << 1) |
                   (1 << 3) |
                   (1 << 4) |
                   (1 << 5));

        for channel in 0..14 {
            let channel_base = 0xc8 + 0x0a*(channel as u16);
            let (enabled, divider, aphase, dphase) = OUTPUT_CONFIG[channel];

            if enabled {
                // Only clock channels need to be high-performance
                if (channel % 2) == 0 { write(channel_base, 0x91); }
                else { write(channel_base, 0x11); }
            }
            else { write(channel_base, 0x10); }
            write(channel_base + 0x1, (divider & 0x0ff) as u8);
            write(channel_base + 0x2, ((divider & 0x700) >> 8) as u8);
            write(channel_base + 0x3, aphase & 0x1f);
            write(channel_base + 0x4, dphase & 0x1f);

            // No analog phase shift on clock channels
            if (channel % 2) == 0 { write(channel_base + 0x7, 0x00); } 
            else { write(channel_base + 0x7, 0x01); }

            write(channel_base + 0x8, 0x08)
        }

        Ok(())
    }
}

pub fn init() -> Result<(), &'static str> {
    clock_mux::init();
    hmc830::init()?;
    hmc7043::init()
}
