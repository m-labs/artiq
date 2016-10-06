#include <generated/csr.h>

#include <stdint.h>
#include <stddef.h>

#include "artiq_personality.h"
#include "ad9154.h"

#ifdef CONFIG_AD9154_DAC_CS

void ad9154_init(void)
{
    ad9154_spi_offline_write(1);
    ad9154_spi_cs_polarity_write(0);
    ad9154_spi_clk_polarity_write(0);
    ad9154_spi_clk_phase_write(0);
    ad9154_spi_lsb_first_write(0);
    ad9154_spi_half_duplex_write(0);
    ad9154_spi_clk_div_write_write(11);
    ad9154_spi_clk_div_read_write(11);
    ad9154_spi_xfer_len_write_write(24);
    ad9154_spi_xfer_len_read_write(0);
    ad9154_spi_cs_write(CONFIG_AD9154_DAC_CS);
    ad9154_spi_offline_write(0);
}

#define AD9_READ (1 << 15)
#define AD9_XFER(w) ((w) << 13)

void ad9154_write(uint16_t addr, uint8_t data)
{
    ad9154_spi_data_write_write(
            ((AD9_XFER(0) | addr) << 16) | (data << 8));
    while (ad9154_spi_pending_read());
    while (ad9154_spi_active_read());
}

uint8_t ad9154_read(uint16_t addr)
{
    ad9154_write(AD9_READ | addr, 0);
    return ad9154_spi_data_read_read();
}

void ad9516_write(uint16_t addr, uint8_t data)
{
    ad9154_spi_cs_write(CONFIG_AD9154_CLK_CS);
    ad9154_write(addr, data);
    ad9154_spi_cs_write(CONFIG_AD9154_DAC_CS);
}

uint8_t ad9516_read(uint16_t addr)
{
    ad9516_write(AD9_READ | addr, 0);
    return ad9154_spi_data_read_read();
}

void jesd_enable(int en)
{
    jesd_control_enable_write(en);
}

int jesd_ready(void)
{
    return jesd_control_ready_read();
}

void jesd_prbs(int p)
{
    jesd_control_prbs_config_write(p);
}

#endif /* CONFIG_AD9154_DAC_CS */
