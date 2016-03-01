from artiq.language.core import (kernel, portable, delay, delay_mu, int)
from artiq.language.units import ns
from artiq.coredevice import spi


_AD53xx_SPI_CONFIG = (0*spi.SPI_OFFLINE | 0*spi.SPI_CS_POLARITY |
                      0*spi.SPI_CLK_POLARITY | 0*spi.SPI_CLK_PHASE |
                      0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX)

_AD53xx_MODE_WRITE_X1 = 3 << 22
_AD53xx_MODE_WRITE_C = 2 << 22
_AD53xx_MODE_WRITE_M = 1 << 22
_AD53xx_MODE_SPECIAL = 0 << 22

_AD53xx_GROUP = portable(lambda g: ((g + 1) << 19))
_AD53xx_GROUP_ALL = 0 << 19
_AD53xx_GROUP_01234 = 6 << 19
_AD53xx_GROUP_1234 = 7 << 19
_AD53xx_CHANNEL_ALL = 0 << 16
_AD53xx_CHANNEL = portable(lambda g: g << 16)

_AD53xx_SPECIAL_NOP = 0 << 16
_AD53xx_SPECIAL_CONTROL = 1 << 16
_AD53xx_SPECIAL_OFS0 = 2 << 16
_AD53xx_SPECIAL_OFS1 = 3 << 16
_AD53xx_SPECIAL_AB_SELECT = portable(lambda i: (i + 6) << 16)
_AD53xx_SPECIAL_AB_SELECT_ALL = 11 << 16

_AD53xx_READ_X1A = portable(lambda ch: (0x00 | (ch + 8)) << 7)
_AD53xx_READ_X1B = portable(lambda ch: (0x40 | (ch + 8)) << 7)
_AD53xx_READ_C = portable(lambda ch: (0x80 | (ch + 8)) << 7)
_AD53xx_READ_M = portable(lambda ch: (0xc0 | (ch + 8)) << 7)
_AD53xx_READ_CONTROL = 0x101 << 7
_AD53xx_READ_OFS0 = 0x102 << 7
_AD53xx_READ_OFS1 = 0x103 << 7
_AD53xx_READ_AB_SELECT = portable(lambda i: (0x100 + (i + 6)) << 7)


class AD53xx:
    def __init__(self, dmgr, spi_bus, ldac=None,
                 chip_select=0, write_div=4, read_div=6):
        self.core = dmgr.get("core")
        self.bus = dmgr.get(spi_bus)
        # if ldac is not None:
        ldac = dmgr.get(ldac)
        self.ldac = ldac
        self.chip_select = chip_select
        self.write_div = write_div
        self.read_div = read_div

    @kernel
    def bus_setup(self):
        self.bus.set_config_mu(_AD53xx_SPI_CONFIG, self.write_div,
                               self.read_div)
        self.bus.set_xfer(self.chip_select, 24, 0)

    @kernel
    def _channel_address(self, channel=0):
        return int((channel + 8) << 16)

    @kernel
    def write_x1(self, channel=0, value=0):
        ch = self._channel_address(channel)
        self.bus.write(_AD53xx_MODE_WRITE_X1 | ch | value)
        delay_mu(int(self.bus.xfer_period_mu + self.bus.write_period_mu))

    @kernel
    def load(self):
        self.ldac.off()
        delay(20*ns)
        self.ldac.on()
