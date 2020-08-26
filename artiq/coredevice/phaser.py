import numpy as np

from artiq.language.core import kernel, delay_mu, delay
from artiq.coredevice.rtio import rtio_output, rtio_input_data
from artiq.language.units import us, ns
from artiq.language.types import TInt32


PHASER_BOARD_ID = 19
PHASER_ADDR_BOARD_ID = 0x00
PHASER_ADDR_HW_REV = 0x01
PHASER_ADDR_GW_REV = 0x02
PHASER_ADDR_CFG = 0x03
PHASER_ADDR_STA = 0x04
PHASER_ADDR_CRC_ERR = 0x05
PHASER_ADDR_LED = 0x06
PHASER_ADDR_FAN = 0x07
PHASER_ADDR_DUC_STB = 0x08
PHASER_ADDR_ADC_CFG = 0x09
PHASER_ADDR_SPI_CFG = 0x0a
PHASER_ADDR_SPI_DIV = 0x0b
PHASER_ADDR_SPI_SEL = 0x0c
PHASER_ADDR_SPI_DATW = 0x0d
PHASER_ADDR_SPI_DATR = 0x0e
# PHASER_ADDR_RESERVED0 = 0x0f
PHASER_ADDR_DUC0_CFG = 0x10
# PHASER_ADDR_DUC0_RESERVED0 = 0x11
PHASER_ADDR_DUC0_F = 0x12
PHASER_ADDR_DUC0_P = 0x16
PHASER_ADDR_DAC0_DATA = 0x18
PHASER_ADDR_DAC0_TEST = 0x1c
PHASER_ADDR_DUC1_CFG = 0x20
# PHASER_ADDR_DUC1_RESERVED0 = 0x21
PHASER_ADDR_DUC1_F = 0x22
PHASER_ADDR_DUC1_P = 0x26
PHASER_ADDR_DAC1_DATA = 0x28
PHASER_ADDR_DAC1_TEST = 0x2c

PHASER_SEL_DAC = 1 << 0
PHASER_SEL_TRF0 = 1 << 1
PHASER_SEL_TRF1 = 1 << 2
PHASER_SEL_ATT0 = 1 << 3
PHASER_SEL_ATT1 = 1 << 4


class Phaser:
    kernel_invariants = {"core", "channel_base", "t_frame"}

    def __init__(self, dmgr, channel_base, miso_delay=1,
                 core_device="core"):
        self.channel_base = channel_base << 8
        self.core = dmgr.get(core_device)
        self.miso_delay = miso_delay
        # frame duration in mu (10 words, 8 clock cycles each 4 ns)
        # self.core.seconds_to_mu(10*8*4*ns)  # unfortunately 319
        self.t_frame = 10*8*4

    @kernel
    def init(self):
        board_id = self.read(PHASER_ADDR_BOARD_ID)
        if board_id != PHASER_BOARD_ID:
            raise ValueError("invalid board id")
        delay(20*us)

    @kernel
    def write(self, addr, data):
        """Write data to a Phaser FPGA register.

        :param addr: Address to write to.
        :param data: Data to write.
        """
        rtio_output(self.channel_base | addr | 0x80, data)
        delay_mu(int64(self.t_frame))

    @kernel
    def read(self, addr):
        """Read from Phaser FPGA register.

        TODO: untested

        :param addr: Address to read from.
        :return: The data read.
        """
        rtio_output(self.channel_base | addr, 0)
        response = rtio_input_data(self.channel_base >> 8)
        return response >> self.miso_delay

    @kernel
    def set_leds(self, leds):
        self.write(PHASER_ADDR_LED, leds)

    @kernel
    def set_fan(self, duty):
        self.write(PHASER_ADDR_FAN, duty)

    @kernel
    def set_cfg(self, clk_sel=0, dac_resetb=1, dac_sleep=0, dac_txena=1,
                trf0_ps=0, trf1_ps=0, att0_rstn=1, att1_rstn=1):
        self.write(PHASER_ADDR_CFG,
            (clk_sel << 0) | (dac_resetb << 1) | (dac_sleep << 2) |
            (dac_txena << 3) | (trf0_ps << 4) | (trf1_ps << 5) |
            (att0_rstn << 6) | (att1_rstn << 7))

    @kernel
    def get_sta(self):
        return self.read(PHASER_ADDR_STA)

    @kernel
    def get_crc_err(self):
        return self.read(PHASER_ADDR_CRC_ERR)

    @kernel
    def get_dac_data(self, ch) -> TInt32:
        data = 0
        for addr in range(4):
            data <<= 8
            data |= self.read(PHASER_ADDR_DAC0_DATA + (ch << 4) + addr)
            delay(20*us)  # slack
        return data

    @kernel
    def set_dac_test(self, ch, data: TInt32):
        for addr in range(4):
            byte = (data >> 24) & 0xff
            self.write(PHASER_ADDR_DAC0_TEST + (ch << 4) + addr, byte)
            data <<= 8
        return data

    @kernel
    def set_duc_cfg(self, ch, clr=0, clr_once=0, select=0):
        self.write(PHASER_ADDR_DUC0_CFG + (ch << 4),
                   (clr << 0) | (clr_once << 1) | (select << 2))

    @kernel
    def spi_cfg(self, select, div, end, clk_phase=0, clk_polarity=0,
                half_duplex=0, lsb_first=0, offline=0):
        self.write(PHASER_ADDR_SPI_SEL, select)
        self.write(PHASER_ADDR_SPI_DIV, div)
        self.write(PHASER_ADDR_SPI_CFG,
                   (offline << 0) | (end << 1) | (clk_phase << 2) |
                   (clk_polarity << 3) | (half_duplex << 4) |
                   (lsb_first << 5))

    @kernel
    def spi_write(self, data):
        self.write(PHASER_ADDR_SPI_DATW, data)

    @kernel
    def spi_read(self):
        return self.read(PHASER_ADDR_SPI_DATR)

    @kernel
    def dac_write(self, addr, data):
        div = 30  # 100 ns min period
        t_xfer = self.core.seconds_to_mu((8 + 1)*(div + 2)*4*ns)
        self.spi_cfg(select=PHASER_SEL_DAC, div=div, end=0)
        self.spi_write(addr)
        delay_mu(t_xfer)
        self.spi_write(data >> 8)
        delay_mu(t_xfer)
        self.spi_cfg(select=PHASER_SEL_DAC, div=div, end=1)
        self.spi_write(data & 0xff)
        delay_mu(t_xfer)

    @kernel
    def dac_read(self, addr, div=30) -> TInt32:
        t_xfer = self.core.seconds_to_mu((8 + 1)*(div + 2)*4*ns)
        self.spi_cfg(select=PHASER_SEL_DAC, div=div, end=0)
        self.spi_write(addr | 0x80)
        delay_mu(t_xfer)
        self.spi_write(0)
        delay_mu(t_xfer)
        data = self.spi_read() << 8
        delay(10*us)  # slack
        self.spi_cfg(select=PHASER_SEL_DAC, div=div, end=1)
        self.spi_write(0)
        delay_mu(t_xfer)
        data |= self.spi_read()
        return data

    @kernel
    def att_write(self, ch, data):
        div = 30  # 30 ns min period
        t_xfer = self.core.seconds_to_mu((8 + 1)*(div + 2)*4*ns)
        self.spi_cfg(select=PHASER_SEL_ATT0 << ch, div=div, end=1)
        self.spi_write(data)
        delay_mu(t_xfer)

    @kernel
    def att_read(self, ch) -> TInt32:
        div = 30
        t_xfer = self.core.seconds_to_mu((8 + 1)*(div + 2)*4*ns)
        self.spi_cfg(select=PHASER_SEL_ATT0 << ch, div=div, end=0)
        self.spi_write(0)
        delay_mu(t_xfer)
        data = self.spi_read()
        delay(10*us)
        self.spi_cfg(select=PHASER_SEL_ATT0 << ch, div=div, end=1)
        self.spi_write(data)
        delay_mu(t_xfer)
        return data
