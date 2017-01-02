use csr;
use ad9516_reg;

fn spi_setup() {
    unsafe {
        csr::converter_spi::offline_write(1);
        csr::converter_spi::cs_polarity_write(0);
        csr::converter_spi::clk_polarity_write(0);
        csr::converter_spi::clk_phase_write(0);
        csr::converter_spi::lsb_first_write(0);
        csr::converter_spi::half_duplex_write(0);
        csr::converter_spi::clk_div_write_write(16);
        csr::converter_spi::clk_div_read_write(16);
        csr::converter_spi::xfer_len_write_write(24);
        csr::converter_spi::xfer_len_read_write(0);
        csr::converter_spi::cs_write(1 << csr::CONFIG_CONVERTER_SPI_CLK_CS);
        csr::converter_spi::offline_write(0);
    }
}

fn write(addr: u16, data: u8) {
    unsafe {
        csr::converter_spi::data_write_write(
            ((addr as u32) << 16) | ((data as u32) << 8));
        while csr::converter_spi::pending_read() != 0 {}
        while csr::converter_spi::active_read() != 0 {}
    }
}

fn read(addr: u16) -> u8 {
    unsafe {
        write((1 << 15) | addr, 0);
        csr::converter_spi::data_read_read() as u8
    }
}

pub fn init() -> Result<(), &'static str> {
    spi_setup();

    write(ad9516_reg::SERIAL_PORT_CONFIGURATION,
            ad9516_reg::SOFT_RESET | ad9516_reg::SOFT_RESET_MIRRORED |
            ad9516_reg::LONG_INSTRUCTION | ad9516_reg::LONG_INSTRUCTION_MIRRORED |
            ad9516_reg::SDO_ACTIVE | ad9516_reg::SDO_ACTIVE_MIRRORED);
    write(ad9516_reg::SERIAL_PORT_CONFIGURATION,
            ad9516_reg::LONG_INSTRUCTION | ad9516_reg::LONG_INSTRUCTION_MIRRORED |
            ad9516_reg::SDO_ACTIVE | ad9516_reg::SDO_ACTIVE_MIRRORED);
    if read(ad9516_reg::PART_ID) != 0x41 {
        return Err("AD9516 not found")
    }

    // use clk input, dclk=clk/2
    write(ad9516_reg::PFD_AND_CHARGE_PUMP, 1*ad9516_reg::PLL_POWER_DOWN |
            0*ad9516_reg::CHARGE_PUMP_MODE);
    write(ad9516_reg::VCO_DIVIDER, 0);
    write(ad9516_reg::INPUT_CLKS, 0*ad9516_reg::SELECT_VCO_OR_CLK |
            0*ad9516_reg::BYPASS_VCO_DIVIDER);

    write(ad9516_reg::OUT0, 2*ad9516_reg::OUT0_POWER_DOWN);
    write(ad9516_reg::OUT2, 2*ad9516_reg::OUT2_POWER_DOWN);
    write(ad9516_reg::OUT3, 2*ad9516_reg::OUT3_POWER_DOWN);
    write(ad9516_reg::OUT4, 2*ad9516_reg::OUT4_POWER_DOWN);
    write(ad9516_reg::OUT5, 2*ad9516_reg::OUT5_POWER_DOWN);
    write(ad9516_reg::OUT8, 1*ad9516_reg::OUT8_POWER_DOWN);

    // DAC deviceclk, clk/1
    write(ad9516_reg::DIVIDER_0_2, ad9516_reg::DIVIDER_0_DIRECT_TO_OUTPUT);
    write(ad9516_reg::OUT1, 0*ad9516_reg::OUT1_POWER_DOWN |
            2*ad9516_reg::OUT1_LVPECLDIFFERENTIAL_VOLTAGE);

    // FPGA deviceclk, dclk/1
    write(ad9516_reg::DIVIDER_4_3, 0*ad9516_reg::DIVIDER_4_NOSYNC |
            1*ad9516_reg::DIVIDER_4_BYPASS_1 | 1*ad9516_reg::DIVIDER_4_BYPASS_2);
    write(ad9516_reg::DIVIDER_4_4, 0*ad9516_reg::DIVIDER_4_DCCOFF);
    write(ad9516_reg::OUT9, 1*ad9516_reg::OUT9_LVDS_OUTPUT_CURRENT |
            2*ad9516_reg::OUT9_LVDS_CMOS_OUTPUT_POLARITY |
            0*ad9516_reg::OUT9_SELECT_LVDS_CMOS);

    // sysref f_data*S/(K*F), dclk/16
    write(ad9516_reg::DIVIDER_3_0, (16/2-1)*ad9516_reg::DIVIDER_3_HIGH_CYCLES_1 |
            (16/2-1)*ad9516_reg::DIVIDER_3_LOW_CYCLES_1);
    write(ad9516_reg::DIVIDER_3_1, 0*ad9516_reg::DIVIDER_3_PHASE_OFFSET_1 |
            0*ad9516_reg::DIVIDER_3_PHASE_OFFSET_2);
    write(ad9516_reg::DIVIDER_3_3, 0*ad9516_reg::DIVIDER_3_NOSYNC |
            0*ad9516_reg::DIVIDER_3_BYPASS_1 | 1*ad9516_reg::DIVIDER_3_BYPASS_2);
    write(ad9516_reg::DIVIDER_3_4, 0*ad9516_reg::DIVIDER_3_DCCOFF);
    write(ad9516_reg::OUT6, 1*ad9516_reg::OUT6_LVDS_OUTPUT_CURRENT |
            2*ad9516_reg::OUT6_LVDS_CMOS_OUTPUT_POLARITY |
            0*ad9516_reg::OUT6_SELECT_LVDS_CMOS);
    write(ad9516_reg::OUT7, 1*ad9516_reg::OUT7_LVDS_OUTPUT_CURRENT |
            2*ad9516_reg::OUT7_LVDS_CMOS_OUTPUT_POLARITY |
            0*ad9516_reg::OUT7_SELECT_LVDS_CMOS);

    write(ad9516_reg::UPDATE_ALL_REGISTERS, 1);

    Ok(())
}
