from artiq.language.core import kernel, portable, delay_mu
from artiq.coredevice import spi

# Designed from the data sheets and somewhat after the linux kernel
# iio driver.

_AD5360_SPI_CONFIG = (0*spi.SPI_OFFLINE | 0*spi.SPI_CS_POLARITY |
                      0*spi.SPI_CLK_POLARITY | 1*spi.SPI_CLK_PHASE |
                      0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX)

_AD5360_CMD_DATA = 3 << 22
_AD5360_CMD_OFFSET = 2 << 22
_AD5360_CMD_GAIN = 1 << 22
_AD5360_CMD_SPECIAL = 0 << 22


@portable
def _AD5360_WRITE_CHANNEL(c):
    return (c + 8) << 16

_AD5360_SPECIAL_NOP = 0 << 16
_AD5360_SPECIAL_CONTROL = 1 << 16
_AD5360_SPECIAL_OFS0 = 2 << 16
_AD5360_SPECIAL_OFS1 = 3 << 16
_AD5360_SPECIAL_READ = 5 << 16


@portable
def _AD5360_READ_CHANNEL(ch):
    return (ch + 8) << 7

_AD5360_READ_X1A = 0x000 << 7
_AD5360_READ_X1B = 0x040 << 7
_AD5360_READ_OFFSET = 0x080 << 7
_AD5360_READ_GAIN = 0x0c0 << 7
_AD5360_READ_CONTROL = 0x101 << 7
_AD5360_READ_OFS0 = 0x102 << 7
_AD5360_READ_OFS1 = 0x103 << 7


class AD5360:
    """
    Support for the Analog devices AD53[67][0123]
    multi-channel Digital to Analog Converters
    """

    def __init__(self, dmgr, spi_device, ldac_device=None,
                 chip_select=1):
        self.core = dmgr.get("core")
        self.bus = dmgr.get(spi_device)
        if ldac_device is not None:
            ldac = dmgr.get(ldac_device)
        self.ldac = ldac
        self.chip_select = chip_select

    @kernel
    def setup_bus(self, write_div=4, read_div=7):
        # write: 2*8ns >= 10ns = t_6 (clk falling to cs_n rising)
        # read: 4*8*ns >= 25ns = t_22 (clk falling to miso valid)
        self.bus.set_config_mu(_AD5360_SPI_CONFIG, write_div, read_div)
        self.bus.set_xfer(self.chip_select, 24, 0)

    @kernel
    def write(self, data):
        self.bus.write(data << 8)
        delay_mu(self.bus.ref_period_mu)  # get to 20ns min cs high

    @kernel
    def write_offsets(self, value=0x1fff):
        value &= 0x3fff
        self.write(_AD5360_CMD_SPECIAL | _AD5360_SPECIAL_OFS0 | value)
        self.write(_AD5360_CMD_SPECIAL | _AD5360_SPECIAL_OFS1 | value)

    @kernel
    def write_channel(self, channel=0, value=0, op=_AD5360_CMD_DATA):
        channel &= 0x3f
        value &= 0xffff
        self.write(op | _AD5360_WRITE_CHANNEL(channel) | value)

    @kernel
    def write_channels(self, values, op=_AD5360_CMD_DATA):
        for i in range(len(values)):
            self.write_channel(i, values[i], op)

    @kernel
    def read_channel_sync(self, channel=0, op=_AD5360_READ_X1A):
        channel &= 0x3f
        self.write(_AD5360_CMD_SPECIAL | _AD5360_SPECIAL_READ | op |
                   _AD5360_READ_CHANNEL(channel))
        self.bus.set_xfer(self.chip_select, 0, 24)
        self.write(_AD5360_CMD_SPECIAL | _AD5360_SPECIAL_NOP)
        self.bus.read_async()
        self.bus.set_xfer(self.chip_select, 24, 0)
        return self.bus.input_async() & 0xffff

    @kernel
    def load(self):
        self.ldac.off()
        delay_mu(3*self.bus.ref_period_mu)
        self.ldac.on()
