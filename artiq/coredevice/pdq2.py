from artiq.language.core import (kernel, portable, delay_mu, delay)
from artiq.language.units import ns, us
from artiq.coredevice import spi


_PDQ2_SPI_CONFIG = (
        0*spi.SPI_OFFLINE | 0*spi.SPI_CS_POLARITY |
        0*spi.SPI_CLK_POLARITY | 0*spi.SPI_CLK_PHASE |
        0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX
        )


@portable
def _PDQ2_CMD(board, is_mem, adr, we):
    return (adr << 0) | (is_mem << 2) | (board << 3) | (we << 7)


_PDQ2_ADR_CONFIG = 0
_PDQ2_ADR_CRC = 1
_PDQ2_ADR_FRAME = 2


class PDQ2:
    """

    :param spi_device: Name of the SPI bus this device is on.
    :param chip_select: Value to drive on the chip select lines
      during transactions.
    """

    def __init__(self, dmgr, spi_device, chip_select=1):
        self.core = dmgr.get("core")
        self.bus = dmgr.get(spi_device)
        self.chip_select = chip_select

    @kernel
    def setup_bus(self, write_div=4, read_div=15):
        """Configure the SPI bus and the SPI transaction parameters
        for this device. This method has to be called before any other method
        if the bus has been used to access a different device in the meantime.

        This method advances the timeline by the duration of two
        RTIO-to-Wishbone bus transactions.

        :param write_div: Write clock divider.
        :param read_div: Read clock divider.
        """
        # write: 4*8ns >= 20ns = 2*clk (clock de-glitching 50MHz)
        # read: 15*8*ns >= ~100ns = 5*clk (clk de-glitching latency + miso
        #   latency)
        self.bus.set_config_mu(_PDQ2_SPI_CONFIG, write_div, read_div)
        self.bus.set_xfer(self.chip_select, 16, 0)

    @kernel
    def write(self, data):
        """Write 16 bits of data.

        This method advances the timeline by the duration of the SPI transfer
        and the required CS high time.
        """
        self.bus.write(data << 16)
        delay_mu(self.bus.ref_period_mu)  # get to 20ns min cs high

    @kernel
    def write_reg(self, adr, data, board):
        self.write((_PDQ2_CMD(board, 0, adr, 1) << 24) | (data << 16))

    @kernel
    def read_reg(self, adr, board):
        self.bus.set_xfer(self.chip_select, 16, 8)
        self.write(_PDQ2_CMD(board, 0, adr, 0) << 24)
        self.bus.read_async()
        self.bus.set_xfer(self.chip_select, 16, 0)
        return self.bus.input_async() & 0xff

    @kernel
    def write_config(self, config, board=0xf):
        self.write_reg(_PDQ2_ADR_CONFIG, config, board)

    @kernel
    def read_config(self, board=0xf):
        return self.read_reg(_PDQ2_ADR_CONFIG, board)

    @kernel
    def write_crc(self, crc, board=0xf):
        self.write_reg(_PDQ2_ADR_CRC, crc, board)

    @kernel
    def read_crc(self, board=0xf):
        return self.read_reg(_PDQ2_ADR_CRC, board)

    @kernel
    def write_frame(self, frame, board=0xf):
        self.write_reg(_PDQ2_ADR_FRAME, frame, board)

    @kernel
    def read_frame(self, board=0xf):
        return self.read_reg(_PDQ2_ADR_FRAME, board)

    @kernel
    def write_mem(self, mem, adr, data, board=0xf):
        pass

    @kernel
    def read_mem(self, mem, adr, data, board=0xf):
        pass
