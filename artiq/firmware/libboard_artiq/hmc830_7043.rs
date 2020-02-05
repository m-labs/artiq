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
        // Warning: Output divider is not synchronized! Set to 1 for deterministic
        // phase at the output.
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

    // Warning: dividers are not synchronized with HMC830 clock input!
    // Set DAC_CLK_DIV to 1 or 0 for deterministic phase.
    // (0 bypasses the divider and reduces noise)
    const DAC_CLK_DIV: u16 = 0;
    const FPGA_CLK_DIV: u16 = 16; // Keep in sync with jdcg.rs
    const SYSREF_DIV: u16 = 256;  // Keep in sync with jdcg.rs
    const HMC_SYSREF_DIV: u16 = SYSREF_DIV*8; // must be <= 4MHz

    // enabled, divider, output config, is sysref
    const OUTPUT_CONFIG: [(bool, u16, u8, bool); 14] = [
        (true,  DAC_CLK_DIV,  0x08, false),  //  0: DAC1_CLK
        (true,  SYSREF_DIV,   0x01, true),   //  1: DAC1_SYSREF
        (true,  DAC_CLK_DIV,  0x08, false),  //  2: DAC0_CLK
        (true,  SYSREF_DIV,   0x01, true),   //  3: DAC0_SYSREF
        (true,  SYSREF_DIV,   0x10, true),   //  4: AMC_FPGA_SYSREF0
        (true,  FPGA_CLK_DIV, 0x10, true),   //  5: AMC_FPGA_SYSREF1
        (false, 0,            0x10, false),  //  6: unused
        (true,  SYSREF_DIV,   0x10, true),   //  7: RTM_FPGA_SYSREF0
        (true,  FPGA_CLK_DIV, 0x08, false),  //  8: GTP_CLK0_IN
        (false, 0,            0x10, false),  //  9: unused
        (false, 0,            0x10, false),  // 10: unused
        (false, 0,            0x08, false),  // 11: unused / uFL
        (false, 0,            0x10, false),  // 12: unused
        (false, SYSREF_DIV,   0x10, true),   // 13: RTM_FPGA_SYSREF1
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

    fn spi_wait_idle() {
        unsafe {
            while csr::converter_spi::idle_read() == 0 {}
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

    const GPO_MUX_CLK_OUT_PHASE: u8 = 3;
    const GPO_MUX_FORCE1: u8 = 10;
    const GPO_MUX_FORCE0: u8 = 11;

    /* Read an HMC7043 internal status bit through the GPO interface.
     * This method is required to work around bugs in the register interface.
     */
    fn gpo_indirect_read(mux_setting: u8) -> bool {
        write(0x50, (mux_setting << 2) | 0x3);
        spi_wait_idle();
        unsafe {
            csr::hmc7043_gpo::in_read() == 1
        }
    }

    pub fn init() {
        spi_setup();
        info!("loading configuration...");

        write(0x3, 0x14);  // Disable the RFSYNCIN reseeder
        write(0xA, 0x06);  // Disable the RFSYNCIN input buffer
        write(0xB, 0x07);  // Enable the CLKIN input as LVPECL
        write(0x9F, 0x4d); // Unexplained high-performance mode
        write(0xA0, 0xdf); // Unexplained high-performance mode

        // Enable required output groups
        let mut output_group_en = 0;
        for channel in 0..OUTPUT_CONFIG.len() {
            let enabled = OUTPUT_CONFIG[channel].0;
            if enabled {
                let group = channel/2;
                output_group_en |= 1 << group;
            }
        }
        write(0x4, output_group_en);

        // Set SYSREF timer divider.
        // We don't need this "feature", but the HMC7043 won't work without.
        write(0x5c, (HMC_SYSREF_DIV & 0xff) as u8);
        write(0x5d, ((HMC_SYSREF_DIV & 0xf00) >> 8) as u8);

        for channel in 0..OUTPUT_CONFIG.len() {
            let channel_base = 0xc8 + 0x0a*(channel as u16);
            let (enabled, divider, outcfg, is_sysref) = OUTPUT_CONFIG[channel];

            if enabled {
                if !is_sysref {
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
            write(channel_base + 0x2, ((divider & 0xf00) >> 8) as u8);

            // bypass analog phase shift on DCLK channels to reduce noise
            if !is_sysref {
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

        clock::spin_us(10_000);

        info!("  ...done");
    }

    pub fn test_gpo() -> Result<(), &'static str> {
        info!("testing GPO...");
        for trial in 0..10 {
            if !gpo_indirect_read(GPO_MUX_FORCE1) {
                info!("  ...failed. GPO I/O did not go high (#{})", trial + 1);
                return Err("GPO is not functioning");
            }
            if gpo_indirect_read(GPO_MUX_FORCE0) {
                info!("  ...failed. GPO I/O did not return low (#{})", trial + 1);
                return Err("GPO is not functioning");
            }
        }
        info!("  ...passed");
        Ok(())
    }

    pub fn check_phased() -> Result<(), &'static str> {
        if !gpo_indirect_read(GPO_MUX_CLK_OUT_PHASE) {
            return Err("GPO reported phases did not align");
        }
        // Should be the same as the GPO read
        let sysref_fsm_status = read(0x91);
        if sysref_fsm_status != 0x2 {
            error!("Bad SYSREF FSM status: {:02x}", sysref_fsm_status);
            return Err("Bad SYSREF FSM status");
        }
        Ok(())
    }

    pub fn unmute() {
        /*
         * Never missing an opportunity to be awful, the HMC7043 produces broadband noise
         * prior to intialization, which can upset the AMC FPGA.
         * External circuitry mutes it.
         */
        unsafe {
            csr::hmc7043_out_en::out_write(1);
        }
    }

    pub fn sysref_delay_dac(dacno: u8, phase_offset: u8) {
        spi_setup();
        if dacno == 0 {
            write(0x00e9, phase_offset);
        } else if dacno == 1 {
            write(0x00d5, phase_offset);
        } else {
            unimplemented!();
        }
        clock::spin_us(100);
    }

    pub fn sysref_slip() {
        spi_setup();
        write(0x0002, 0x02);
        write(0x0002, 0x00);
        clock::spin_us(100);
    }
}

pub fn init() -> Result<(), &'static str> {
    #[cfg(all(hmc830_ref = "125", rtio_frequency = "125.0"))]
    const DIV: (u32, u32, u32, u32) = (2, 32, 0, 1); // 125MHz -> 2.0GHz
    #[cfg(all(hmc830_ref = "150", rtio_frequency = "150.0"))]
    const DIV: (u32, u32, u32, u32) = (2, 32, 0, 1); // 150MHz -> 2.4GHz

    /* do not use other SPI devices before HMC830 SPI mode selection */
    hmc830::select_spi_mode();
    hmc830::detect()?;
    hmc830::init();

    hmc830::set_dividers(DIV.0, DIV.1, DIV.2, DIV.3);

    hmc830::check_locked()?;

    if hmc7043::get_id() == hmc7043::CHIP_ID {
        error!("HMC7043 detected while in reset (board rework missing?)");
    }
    hmc7043::enable();
    hmc7043::detect()?;
    hmc7043::init();
    hmc7043::test_gpo()?;
    hmc7043::check_phased()?;
    hmc7043::unmute();

    Ok(())
}
