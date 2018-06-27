mod clock_mux {
    use board_misoc::csr;

    const CLK_SRC_EXT_SEL : u8 = 1 << 0;
    const REF_CLK_SRC_SEL : u8 = 1 << 1;
    const DAC_CLK_SRC_SEL : u8 = 1 << 2;
    const REF_LO_CLK_SEL  : u8 = 1 << 3;

    pub fn init() {
        unsafe {
            csr::clock_mux::out_write(
                1*CLK_SRC_EXT_SEL |  // use ext clk from sma
                1*REF_CLK_SRC_SEL |
                1*DAC_CLK_SRC_SEL |
                0*REF_LO_CLK_SEL);
        }
    }
}

mod hmc830 {
    use board_misoc::{csr, clock};

    fn spi_setup() {
        unsafe {
            while csr::converter_spi::idle_read() == 0 {}
            csr::converter_spi::offline_write(0);
            csr::converter_spi::end_write(1);
            csr::converter_spi::cs_polarity_write(0b0001);
            csr::converter_spi::clk_polarity_write(0);
            csr::converter_spi::clk_phase_write(0);
            csr::converter_spi::lsb_first_write(0);
            csr::converter_spi::half_duplex_write(0);
            csr::converter_spi::length_write(32 - 1);
            csr::converter_spi::div_write(16 - 2);
            csr::converter_spi::cs_write(1 << csr::CONFIG_CONVERTER_SPI_HMC830_CS);
        }
    }

    pub fn select_spi_mode() {
        spi_setup();
        unsafe {
            // rising egde on CS since cs_polarity still 0
            // selects "HMC Mode"
            // do a dummy cycle with cs still high to clear CS
            csr::converter_spi::length_write(0);
            csr::converter_spi::data_write(0);
            while csr::converter_spi::writable_read() == 0 {}
            csr::converter_spi::length_write(32 - 1);
        }
    }

    fn write(addr: u8, data: u32) {
        let val = ((addr as u32) << 24) | data;
        unsafe {
            while csr::converter_spi::writable_read() == 0 {}
            csr::converter_spi::data_write(val << 1);  // last clk cycle loads data
        }
    }

    fn read(addr: u8) -> u32 {
        // SDO (miso/read bits) is technically CPHA=1, while SDI is CPHA=0
        // trust that the 8.2ns+0.2ns/pF provide enough hold time on top of
        // the SPI round trip delay and stick with CPHA=0
        write((1 << 6) | addr, 0);
        unsafe {
            while csr::converter_spi::writable_read() == 0 {}
            csr::converter_spi::data_read() & 0xffffff
        }
    }

    pub fn detect() -> Result<(), &'static str> {
        spi_setup();
        let id = read(0x00);
        if id != 0xa7975 {
            error!("invalid HMC830 ID: 0x{:08x}", id);
            return Err("invalid HMC830 identification");
        } else {
            info!("HMC830 found");
        }

        Ok(())
    }

    pub fn init() {
        // Configure HMC830 for integer-N operation
        // See "PLLs with integrated VCO- RF Applications Product & Operating
        // Guide"
        spi_setup();
        info!("loading HMC830 configuration...");

        write(0x0, 0x20);    // software reset
        write(0x0, 0x00);    // normal operation
        write(0x6, 0x307ca); // integer-N mode (NB data sheet table 5.8 not self-consistent)
        write(0x7, 0x4d);    // digital lock detect, 1/2 cycle window (6.5ns window)
        write(0x9, 0x2850);  // charge pump: 1.6mA, no offset
        write(0xa, 0x2045);  // for wideband devices like the HMC830
        write(0xb, 0x7c061); // for HMC830

        // VCO subsystem registers
        // NB software reset does not seem to reset these registers, so always
        // program them all!
        write(0x5, 0xf88);   // 1: defaults
        write(0x5, 0x6010);  // 2: mute output until output divider set
        write(0x5, 0x2818);  // 3: wideband PLL defaults
        write(0x5, 0x60a0);  // 4: HMC830 magic value
        write(0x5, 0x1628);  // 5: HMC830 magic value
        write(0x5, 0x7fb0);  // 6: HMC830 magic value
        write(0x5, 0x0);     // ready for VCO auto-cal

        info!("  ...done");
    }

    pub fn set_dividers(r_div: u32, n_div: u32, m_div: u32, out_div: u32) {
        // VCO frequency: f_vco = (f_ref/r_div)*(n_int + n_frac/2**24)
        // VCO frequency range [1.5GHz, 3GHz]
        // Output frequency: f_out = f_vco/out_div
        // Max PFD frequency: 125MHz for integer-N, 100MHz for fractional
        // (mode B)
        // Max reference frequency: 350MHz, however f_ref >= 200MHz requires
        //     setting 0x08[21]=1
        //
        // :param r_div: reference divider [1, 16383]
        // :param n_div: VCO divider, integer part. Integer-N mode: [16, 2**19-1]
        //    fractional mode: [20, 2**19-4]
        // :param m_div: VCO divider, fractional part [0, 2**24-1]
        // :param out_div: output divider [1, 62] (0 mutes output)
        info!("setting HMC830 dividers...");
        write(0x5, 0x6010 + (out_div << 7) + (((out_div <= 2) as u32) << 15));
        write(0x5, 0x0);     // ready for VCO auto-cal
        write(0x2, r_div);
        write(0x4, m_div);
        write(0x3, n_div);

        info!("  ...done");
    }

    pub fn check_locked() -> Result<(), &'static str> {
        info!("waiting for HMC830 lock...");
        let t = clock::get_ms();
        while read(0x12) & 0x02 == 0 {
            if clock::get_ms() > t + 2000 {
                error!("lock timeout. Register dump:");
                for addr in 0x00..0x14 {
                    // These registers don't exist (in the data sheet at least)
                    if addr == 0x0d || addr == 0x0e { continue; }
                    error!("  [0x{:02x}] = 0x{:04x}", addr, read(addr));
                }
                return Err("lock timeout");
            }
        }
        info!("  ...locked");

        Ok(())
    }
}

pub mod hmc7043 {
    use board_misoc::{csr, clock};

    // All frequencies assume 1.2GHz HMC830 output
    pub const DAC_CLK_DIV: u16 = 2;               // 600MHz
    pub const FPGA_CLK_DIV: u16 = 8;              // 150MHz
    pub const SYSREF_DIV: u16 = 128;              // 9.375MHz
    pub const HMC_SYSREF_DIV: u16 = SYSREF_DIV*8; // 1.171875MHz (must be <= 4MHz)

    // enabled, divider, output config
    const OUTPUT_CONFIG: [(bool, u16, u8); 14] = [
        (true,  DAC_CLK_DIV,  0x08),  // 0: DAC2_CLK
        (true,  SYSREF_DIV,   0x08),  // 1: DAC2_SYSREF
        (true,  DAC_CLK_DIV,  0x08),  // 2: DAC1_CLK
        (true,  SYSREF_DIV,   0x08),  // 3: DAC1_SYSREF
        (false, 0,            0x08),  // 4: ADC2_CLK
        (false, 0,            0x08),  // 5: ADC2_SYSREF
        (true,  FPGA_CLK_DIV, 0x08),  // 6: GTP_CLK2
        (true,  SYSREF_DIV,   0x10),  // 7: FPGA_DAC_SYSREF, LVDS
        (true,  FPGA_CLK_DIV, 0x08),  // 8: GTP_CLK1
        (false, 0,            0x10),  // 9: AMC_MASTER_AUX_CLK
        (false, 0,            0x10),  // 10: RTM_MASTER_AUX_CLK
        (true,  FPGA_CLK_DIV, 0x10),  // 11: FPGA_ADC_SYSREF, LVDS -- repurposed for siphaser
        (false, 0,            0x08),  // 12: ADC1_CLK
        (false, 0,            0x08),  // 13: ADC1_SYSREF
    ];

    fn spi_setup() {
        unsafe {
            while csr::converter_spi::idle_read() == 0 {}
            csr::converter_spi::offline_write(0);
            csr::converter_spi::end_write(1);
            csr::converter_spi::cs_polarity_write(0b0001);
            csr::converter_spi::clk_polarity_write(0);
            csr::converter_spi::clk_phase_write(0);
            csr::converter_spi::lsb_first_write(0);
            csr::converter_spi::half_duplex_write(0);  // change mid-transaction for reads
            csr::converter_spi::length_write(24 - 1);
            csr::converter_spi::div_write(16 - 2);
            csr::converter_spi::cs_write(1 << csr::CONFIG_CONVERTER_SPI_HMC7043_CS);
        }
    }

    fn write(addr: u16, data: u8) {
        let cmd = (0 << 15) | addr;
        let val = ((cmd as u32) << 8) | data as u32;
        unsafe {
            while csr::converter_spi::writable_read() == 0 {}
            csr::converter_spi::data_write(val << 8);
        }
    }

    fn read(addr: u16) -> u8 {
        let cmd = (1 << 15) | addr;
        let val = cmd as u32;
        unsafe {
            while csr::converter_spi::writable_read() == 0 {}
            csr::converter_spi::end_write(0);
            csr::converter_spi::length_write(16 - 1);
            csr::converter_spi::data_write(val << 16);
            while csr::converter_spi::writable_read() == 0 {}
            csr::converter_spi::end_write(1);
            csr::converter_spi::half_duplex_write(1);
            csr::converter_spi::length_write(8 - 1);
            csr::converter_spi::data_write(0);
            while csr::converter_spi::writable_read() == 0 {}
            csr::converter_spi::half_duplex_write(0);
            csr::converter_spi::length_write(24 - 1);
            csr::converter_spi::data_read() as u8
        }
    }

    pub const CHIP_ID: u32 = 0xf17904;

    pub fn get_id() -> u32 {
        spi_setup();
        (read(0x78) as u32) << 16 | (read(0x79) as u32) << 8 | read(0x7a) as u32
    }

    pub fn detect() -> Result<(), &'static str> {
        let id = get_id();
        if id != CHIP_ID {
            error!("invalid HMC7043 ID: 0x{:08x}", id);
            return Err("invalid HMC7043 identification");
        } else {
            info!("HMC7043 found");
        }

        Ok(())
    }

    pub fn enable() {
        info!("enabling HMC7043");

        unsafe {
            csr::hmc7043_reset::out_write(0);
        }
        clock::spin_us(10_000);

        spi_setup();
        write(0x0, 0x1);   // Software reset
        write(0x0, 0x0);   // Normal operation
        write(0x1, 0x48);  // mute all outputs
    }

    pub fn init() {
        spi_setup();
        info!("loading configuration...");

        write(0xA, 0x06);  // Disable the REFSYNCIN input
        write(0xB, 0x07);  // Enable the CLKIN input as LVPECL
        write(0x50, 0x1f); // Disable GPO pin
        write(0x9F, 0x4d); // Unexplained high-performance mode
        write(0xA0, 0xdf); // Unexplained high-performance mode

        // Enable required output groups
        write(0x4, (1 << 0) |
                   (1 << 1) |
                   (1 << 3) |
                   (1 << 4));

        write(0x5c, (HMC_SYSREF_DIV & 0xff) as u8);  // Set SYSREF timer divider
        write(0x5d, ((HMC_SYSREF_DIV & 0x0f) >> 8) as u8);

        for channel in 0..OUTPUT_CONFIG.len() {
            let channel_base = 0xc8 + 0x0a*(channel as u16);
            let (enabled, divider, outcfg) = OUTPUT_CONFIG[channel];

            if enabled {
                if channel % 2 == 0 {
                    // DCLK channel: enable high-performance mode
                    write(channel_base, 0xd1);
                } else {
                    // SYSREF channel: disable hi-perf mode, enable slip
                    write(channel_base, 0x71);
                }
            } else {
                write(channel_base, 0x10);
            }
            write(channel_base + 0x1, (divider & 0xff) as u8);
            write(channel_base + 0x2, ((divider & 0x0f) >> 8) as u8);

            // bypass analog phase shift on DCLK channels to reduce noise
            if channel % 2 == 0 {
                if divider != 0 {
                    write(channel_base + 0x7, 0x00); // enable divider
                } else {
                    write(channel_base + 0x7, 0x03); // bypass divider for lowest noise
                }
            } else {
                write(channel_base + 0x7, 0x01);
            }

            write(channel_base + 0x8, outcfg)
        }

        write(0x1, 0x4a);  // Reset dividers and FSMs
        write(0x1, 0x48);
        write(0x1, 0xc8);  // Synchronize dividers
        write(0x1, 0x40);  // Unmute, high-performance/low-noise mode

        info!("  ...done");
    }

    pub fn sysref_offset_dac(dacno: u8, phase_offset: u16) {
        /*  Analog delay resolution: 25ps
         *  Digital delay resolution: 1/2 input clock cycle = 416ps for 1.2GHz
         *  16*25ps = 400ps: limit analog delay to 16 steps instead of 32.
         */
        let analog_delay = (phase_offset % 17) as u8;
        let digital_delay = (phase_offset / 17) as u8;
        spi_setup();
        if dacno == 0 {
            write(0x00d5, analog_delay);
            write(0x00d6, digital_delay);
        } else if dacno == 1 {
            write(0x00e9, analog_delay);
            write(0x00ea, digital_delay);
        } else {
            unimplemented!();
        }
    }

    fn sysref_offset_fpga(phase_offset: u16) {
        let analog_delay = (phase_offset % 17) as u8;
        let digital_delay = (phase_offset / 17) as u8;
        spi_setup();
        write(0x0111, analog_delay);
        write(0x0112, digital_delay);
    }

    fn sysref_slip() {
        spi_setup();
        write(0x0002, 0x02);
        write(0x0002, 0x00);
    }

    fn sysref_sample() -> bool {
        unsafe { csr::sysref_sampler::sample_result_read() == 1 }
    }

    pub fn sysref_rtio_align(phase_offset: u16, expected_align: u16) {
        info!("aligning SYSREF with RTIO...");

        let mut slips0 = 0;
        let mut slips1 = 0;
        // meet setup/hold (assuming FPGA timing margins are OK)
        sysref_offset_fpga(phase_offset);
        // if we are already in the 1 zone, get out of it
        while sysref_sample() {
            sysref_slip();
            slips0 += 1;
            if slips0 > 1024 {
                error!("  failed to reach 1->0 transition");
                break;
            }
        }
        // get to the edge of the 0->1 transition (our final setpoint)
        while !sysref_sample() {
            sysref_slip();
            slips1 += 1;
            if slips1 > 1024 {
                error!("  failed to reach 0->1 transition");
                break;
            }
        }
        info!("  ...done ({}/{} slips)", slips0, slips1);
        if (slips0 + slips1) % expected_align != 0 {
            error!("  unexpected slip alignment");
        }

        let mut margin_minus = None;
        for d in 0..phase_offset {
            sysref_offset_fpga(phase_offset - d);
            if !sysref_sample() {
                margin_minus = Some(d);
                break;
            }
        }
        // meet setup/hold
        sysref_offset_fpga(phase_offset);

        if margin_minus.is_some() {
            let margin_minus = margin_minus.unwrap();
            // one phase slip (period of the 1.2GHz input clock)
            let period = 2*17; // approximate: 2 digital coarse delay steps
            let margin_plus = if period > margin_minus { period - margin_minus } else { 0 };
            info!("  margins at FPGA: -{} +{}", margin_minus, margin_plus);
            if margin_minus < 10 || margin_plus < 10 {
                error!("SYSREF margin at FPGA is too small");
            }
        } else {
            error!("unable to determine SYSREF margin at FPGA");
        }
    }
}

pub fn init() -> Result<(), &'static str> {
    clock_mux::init();
    /* do not use other SPI devices before HMC830 SPI mode selection */
    hmc830::select_spi_mode();
    hmc830::detect()?;
    hmc830::init();

    // 1.2GHz out
    #[cfg(hmc830_ref = "100")]
    hmc830::set_dividers(1, 24, 0, 2);
    #[cfg(hmc830_ref = "150")]
    hmc830::set_dividers(2, 32, 0, 2);

    hmc830::check_locked()?;

    if hmc7043::get_id() == hmc7043::CHIP_ID {
        error!("HMC7043 detected while in reset (board rework missing?)");
    }
    hmc7043::enable();
    hmc7043::detect()?;
    hmc7043::init();

    Ok(())
}
