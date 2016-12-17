use bsp::board::csr;

pub extern fn init() {
    unsafe {
        csr::ad9154::spi_offline_write(1);
        csr::ad9154::spi_cs_polarity_write(0);
        csr::ad9154::spi_clk_polarity_write(0);
        csr::ad9154::spi_clk_phase_write(0);
        csr::ad9154::spi_lsb_first_write(0);
        csr::ad9154::spi_half_duplex_write(0);
        csr::ad9154::spi_clk_div_write_write(16);
        csr::ad9154::spi_clk_div_read_write(16);
        csr::ad9154::spi_xfer_len_write_write(24);
        csr::ad9154::spi_xfer_len_read_write(0);
        csr::ad9154::spi_cs_write(csr::CONFIG_AD9154_DAC_CS);
        csr::ad9154::spi_offline_write(0);
    }
}

const AD9_READ: u16 = 1 << 15;

pub extern fn dac_write(addr: u16, data: u8) {
    unsafe {
        csr::ad9154::spi_data_write_write(
            ((addr as u32) << 16) | ((data as u32) << 8));
        while csr::ad9154::spi_pending_read() != 0 {}
        while csr::ad9154::spi_active_read() != 0 {}
    }
}

pub extern fn dac_read(addr: u16) -> u8 {
    unsafe {
        dac_write(AD9_READ | addr, 0);
        csr::ad9154::spi_data_read_read() as u8
    }
}

pub extern fn clk_write(addr: u16, data: u8) {
    unsafe {
        csr::ad9154::spi_cs_write(csr::CONFIG_AD9154_CLK_CS);
        dac_write(addr, data);
        csr::ad9154::spi_cs_write(csr::CONFIG_AD9154_DAC_CS);
    }
}

pub extern fn clk_read(addr: u16) -> u8 {
    unsafe {
        clk_write(AD9_READ | addr, 0);
        csr::ad9154::spi_data_read_read() as u8
    }
}

pub extern fn jesd_enable(en: u32) {
    unsafe {
        csr::ad9154::jesd_control_enable_write(en);
    }
}

pub extern fn jesd_ready() {
    unsafe {
        csr::ad9154::jesd_control_ready_read();
    }
}

pub extern fn jesd_prbs(p: u32) {
    unsafe {
        csr::ad9154::jesd_control_prbs_config_write(p);
    }
}

pub extern fn jesd_stpl(en: u32) {
    unsafe {
        csr::ad9154::jesd_control_stpl_enable_write(en);
    }
}
