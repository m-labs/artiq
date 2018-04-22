"""RTIO driver for the Zotino 32-channel, 16-bit 1MSPS DAC.

Output event replacement is not supported and issuing commands at the same
time is an error.
"""

from artiq.language.core import kernel
from artiq.coredevice import spi2 as spi
from artiq.coredevice.ad53xx import SPI_AD53XX_CONFIG, AD53xx

_SPI_SR_CONFIG = (0*spi.SPI_OFFLINE | 1*spi.SPI_END |
                  0*spi.SPI_INPUT | 0*spi.SPI_CS_POLARITY |
                  0*spi.SPI_CLK_POLARITY | 0*spi.SPI_CLK_PHASE |
                  0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX)

_SPI_CS_DAC = 1
_SPI_CS_SR = 2


class Zotino(AD53xx):
    """ Zotino 32-channel, 16-bit 1MSPS DAC.

    Controls the AD5372 DAC and the 8 user LEDs via a shared SPI interface.

    :param spi_device: SPI bus device name
    :param ldac_device: LDAC RTIO TTLOut channel name.
    :param clr_device: CLR RTIO TTLOut channel name.
    :param div_write: SPI clock divider for write operations (default: 4,
      50MHz max SPI clock)
    :param div_read: SPI clock divider for read operations (default: 8, not
      optimized for speed, but cf data sheet t22: 25ns min SCLK edge to SDO
      valid)
    :param vref: DAC reference voltage (default: 5.)
    :param core_device: Core device name (default: "core")
    """

    def __init__(self, dmgr, spi_device, ldac_device=None, clr_device=None,
                 div_write=4, div_read=8, vref=5., core="core"):
        AD53xx.__init__(self, dmgr=dmgr, spi_device=spi_device,
                        ldac_device=ldac_device, clr_device=clr_device,
                        chip_select=_SPI_CS_DAC, div_write=div_write,
                        div_read=div_read, core=core)

    @kernel
    def set_leds(self, leds):
        """ Sets the states of the 8 user LEDs.

        :param leds: 8-bit word with LED state
        """
        self.bus.set_config_mu(_SPI_SR_CONFIG, 8, self.div_write, _SPI_CS_SR)
        self.bus.write(leds << 24)
        self.bus.set_config_mu(SPI_AD53XX_CONFIG, 24, self.div_write,
                               self.chip_select)
