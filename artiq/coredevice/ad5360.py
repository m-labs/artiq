"""
Driver for the AD5360 DAC on RTIO.

Output event replacement is not supported and issuing commands at the same
time is an error.
"""


from artiq.language.core import (kernel, portable, delay_mu, delay, now_mu,
                                 at_mu)
from artiq.language.units import ns, us
from artiq.coredevice import spi2 as spi

# Designed from the data sheets and somewhat after the linux kernel
# iio driver.

_AD5360_SPI_CONFIG = (0*spi.SPI_OFFLINE | 1*spi.SPI_END |
                      0*spi.SPI_INPUT | 0*spi.SPI_CS_POLARITY |
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

    :param spi_device: Name of the SPI bus this device is on.
    :param ldac_device: Name of the TTL device that LDAC is connected to
      (optional). Needs to be explicitly initialized to high.
    :param chip_select: Value to drive on the chip select lines
      during transactions.
    :param div_write: SPI clock divider during writes
    :param div_read: SPI clock divider during reads
    """
    kernel_invariants = {"bus", "core", "chip_select", "div_read", "div_write"}

    def __init__(self, dmgr, spi_device, ldac_device=None, chip_select=1,
                 div_write=4, div_read=7):
        self.core = dmgr.get("core")
        self.bus = dmgr.get(spi_device)
        if ldac_device is not None:
            self.ldac = dmgr.get(ldac_device)
        self.chip_select = chip_select
        # write: 2*8ns >= 10ns = t_6 (clk falling to cs_n rising)
        # 4*8ns >= 20ns = t_1 (clk cycle time)
        self.div_write = div_write
        # read: 4*8*ns >= 25ns = t_22 (clk falling to miso valid)
        self.div_read = div_read

    @kernel
    def setup_bus(self):
        """Configure the SPI bus and the SPI transaction parameters
        for this device. This method has to be called before any other method
        if the bus has been used to access a different device in the meantime.

        This method advances the timeline by one coarse RTIO cycle.
        """
        self.bus.set_config_mu(_AD5360_SPI_CONFIG, 24, self.div_write,
                               self.chip_select)

    @kernel
    def write(self, data):
        """Write 24 bits of data.

        This method advances the timeline by the duration of the SPI transfer
        and the required CS high time.
        """
        self.bus.write(data << 8)
        delay_mu(self.bus.ref_period_mu)  # get to 20ns min cs high

    @kernel
    def write_offsets(self, value=0x1fff):
        """Write the OFS0 and OFS1 offset DACs.

        This method advances the timeline by twice the duration of
        :meth:`write`.

        :param value: Value to set both offset registers to.
        """
        value &= 0x3fff
        self.write(_AD5360_CMD_SPECIAL | _AD5360_SPECIAL_OFS0 | value)
        self.write(_AD5360_CMD_SPECIAL | _AD5360_SPECIAL_OFS1 | value)

    @kernel
    def write_channel(self, channel=0, value=0, op=_AD5360_CMD_DATA):
        """Write to a channel register.

        This method advances the timeline by the duration of :meth:`write`.

        :param channel: Channel number to write to.
        :param value: 16 bit value to write to the register.
        :param op: Operation to perform, one of :const:`_AD5360_CMD_DATA`,
          :const:`_AD5360_CMD_OFFSET`, :const:`_AD5360_CMD_GAIN`
          (default: :const:`_AD5360_CMD_DATA`).
        """
        channel &= 0x3f
        value &= 0xffff
        self.write(op | _AD5360_WRITE_CHANNEL(channel) | value)

    @kernel
    def read_channel_sync(self, channel=0, op=_AD5360_READ_X1A):
        """Read a channel register.

        This method advances the timeline by the duration of two :meth:`write`
        plus two coarse RTIO cycles.

        :param channel: Channel number to read from.
        :param op: Operation to perform, one of :const:`_AD5360_READ_X1A`,
          :const:`_AD5360_READ_X1B`, :const:`_AD5360_READ_OFFSET`,
          :const:`_AD5360_READ_GAIN` (default: :const:`_AD5360_READ_X1A`).
        :return: The 16 bit register value.
        """
        channel &= 0x3f
        self.write(_AD5360_CMD_SPECIAL | _AD5360_SPECIAL_READ | op |
                   _AD5360_READ_CHANNEL(channel))
        self.bus.set_config_mu(_AD5360_SPI_CONFIG | spi.SPI_INPUT, 24,
                               self.div_read, self.chip_select)
        delay(270*ns)  # t_21 min sync high in readback
        self.write(_AD5360_CMD_SPECIAL | _AD5360_SPECIAL_NOP)
        self.bus.set_config_mu(_AD5360_SPI_CONFIG, 24,
                               self.div_write, self.chip_select)
        return self.bus.read() & 0xffff

    @kernel
    def load(self):
        """Pulse the LDAC line.

        This method advances the timeline by two RTIO clock periods (16 ns).
        """
        self.ldac.off()
        # t13 = 10ns ldac pulse width low
        delay_mu(2*self.bus.ref_period_mu)
        self.ldac.on()

    @kernel
    def set(self, values, op=_AD5360_CMD_DATA):
        """Write to several channels and pulse LDAC to update the channels.

        This method does not advance the timeline. Write events are scheduled
        in the past. The DACs will synchronously start changing their output
        levels `now`.

        :param values: List of 16 bit values to write to the channels.
        :param op: Operation to perform, one of :const:`_AD5360_CMD_DATA`,
          :const:`_AD5360_CMD_OFFSET`, :const:`_AD5360_CMD_GAIN`
          (default: :const:`_AD5360_CMD_DATA`).
        """
        t0 = now_mu()
        # t10 max busy low for one channel
        t_10 = self.core.seconds_to_mu(1.5*us)
        # compensate all delays that will be applied
        delay_mu(-t_10-len(values)*(
            self.bus.ref_period_mu + self.bus.xfer_duration_mu))
        for i in range(len(values)):
            self.write_channel(i, values[i], op)
        delay_mu(t_10)
        self.load()
        at_mu(t0)
