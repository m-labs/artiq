"""
Driver for the AD9912 DDS.
"""


from artiq.language.core import kernel, delay_mu
from artiq.language.units import ns, us
from artiq.coredevice import spi


_AD9912_SPI_CONFIG = (0*spi.SPI_OFFLINE | 0*spi.SPI_CS_POLARITY |
                      0*spi.SPI_CLK_POLARITY | 0*spi.SPI_CLK_PHASE |
                      0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX)


class AD9912:
    """
    Support for the Analog devices AD9912 DDS

    :param spi_device: Name of the SPI bus this device is on.
    :param chip_select: Value to drive on the chip select lines
      during transactions.
    """

    def __init__(self, dmgr, spi_device, chip_select):
        self.core = dmgr.get("core")
        self.bus = dmgr.get(spi_device)
        self.chip_select = chip_select

    @kernel
    def setup_bus(self, write_div=5, read_div=20):
        """Configure the SPI bus and the SPI transaction parameters
        for this device. This method has to be called before any other method
        if the bus has been used to access a different device in the meantime.

        This method advances the timeline by the duration of two
        RTIO-to-Wishbone bus transactions.

        :param write_div: Write clock divider.
        :param read_div: Read clock divider.
        """
        # write: 5*8ns >= 40ns = t_clk (typ clk rate)
        # read: 2*8*ns >= 25ns = t_dv (clk falling to miso valid) + RTT
        self.bus.set_config_mu(_AD9912_SPI_CONFIG, write_div, read_div)
        self.bus.set_xfer(self.chip_select, 24, 0)

    @kernel
    def write(self, data):
        """Write 24 bits of data.

        This method advances the timeline by the duration of the SPI transfer
        and the required CS high time.
        """
        self.bus.write(data << 8)
        delay_mu(self.bus.ref_period_mu)  # get to 20ns min cs high
