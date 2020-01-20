"""RTIO driver for the Analog Devices ADF[45]35[56] family of GHz PLLs
on Mirny-style prefixed SPI buses.
"""

# https://github.com/analogdevicesinc/linux/blob/master/Documentation/devicetree/bindings/iio/frequency/adf5355.txt
# https://github.com/analogdevicesinc/linux/blob/master/drivers/iio/frequency/adf5355.c
# https://www.analog.com/media/en/technical-documentation/data-sheets/ADF5356.pdf
# https://www.analog.com/media/en/technical-documentation/data-sheets/ADF5355.pdf
# https://www.analog.com/media/en/technical-documentation/user-guides/EV-ADF5356SD1Z-UG-1087.pdf


from artiq.language.core import kernel, delay
from artiq.language.units import us
from artiq.coredevice import spi2 as spi

SPI_CONFIG = (0*spi.SPI_OFFLINE | 0*spi.SPI_END |
              0*spi.SPI_INPUT | 1*spi.SPI_CS_POLARITY |
              0*spi.SPI_CLK_POLARITY | 0*spi.SPI_CLK_PHASE |
              0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX)


class ADF5355:
    """Analog Devices AD[45]35[56] family of GHz PLLs.

    :param cpld_device: Mirny CPLD device name
    :param sw_device: Mirny RF switch device name
    :param channel: Mirny RF channel index
    :param core_device: Core device name (default: "core")
    """
    kernel_invariants = {"cpld", "sw", "channel", "core"}

    def __init__(self, dmgr, cpld_device, sw_device, channel,
                 core="core"):
        self.cpld = dmgr.get(cpld_device)
        self.sw = dmgr.get(sw_device)
        self.channel = channel
        self.core = dmgr.get(core)

    @kernel
    def set_att_mu(self, att):
        """Set digital step attenuator in machine units.

        :param att: Attenuation setting, 8 bit digital.
        """
        self.cpld.set_att_mu(self.channel, att)

    @kernel
    def write(self, data):
        self.cpld.write_ext(self.channel | 4, 32, data)

    @kernel
    def read_muxout(self):
        return bool(self.cpld.read_reg(0) & (1 << (self.channel + 8)))

    @kernel
    def init(self):
        self.write((1 << 27) | 4)
        if not self.read_muxout():
            raise ValueError("MUXOUT not high")
        delay(100*us)
        self.write((2 << 27) | 4)
        if self.read_muxout():
            raise ValueError("MUXOUT not low")
        delay(100*us)
        self.write((6 << 27) | 4)
