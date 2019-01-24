""""RTIO driver for the Analog Devices AD53[67][0123] family of multi-channel
Digital to Analog Converters.

Output event replacement is not supported and issuing commands at the same
time is an error.
"""

# Designed from the data sheets and somewhat after the linux kernel
# iio driver.

from numpy import int32

from artiq.language.core import (kernel, portable, delay_mu, delay, now_mu,
                                 at_mu)
from artiq.language.units import ns, us
from artiq.coredevice import spi2 as spi

SPI_AD53XX_CONFIG = (0*spi.SPI_OFFLINE | 1*spi.SPI_END |
                     0*spi.SPI_INPUT | 0*spi.SPI_CS_POLARITY |
                     0*spi.SPI_CLK_POLARITY | 1*spi.SPI_CLK_PHASE |
                     0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX)

AD53XX_CMD_DATA = 3 << 22
AD53XX_CMD_OFFSET = 2 << 22
AD53XX_CMD_GAIN = 1 << 22
AD53XX_CMD_SPECIAL = 0 << 22

AD53XX_SPECIAL_NOP = 0 << 16
AD53XX_SPECIAL_CONTROL = 1 << 16
AD53XX_SPECIAL_OFS0 = 2 << 16
AD53XX_SPECIAL_OFS1 = 3 << 16
AD53XX_SPECIAL_READ = 5 << 16
AD53XX_SPECIAL_AB0 = 6 << 16
AD53XX_SPECIAL_AB1 = 7 << 16
AD53XX_SPECIAL_AB2 = 8 << 16
AD53XX_SPECIAL_AB3 = 9 << 16
AD53XX_SPECIAL_AB = 11 << 16

# incorporate the channel offset (8, table 17) here
AD53XX_READ_X1A = 0x008 << 7
AD53XX_READ_X1B = 0x048 << 7
AD53XX_READ_OFFSET = 0x088 << 7
AD53XX_READ_GAIN = 0x0C8 << 7

AD53XX_READ_CONTROL = 0x101 << 7
AD53XX_READ_OFS0 = 0x102 << 7
AD53XX_READ_OFS1 = 0x103 << 7
AD53XX_READ_AB0 = 0x106 << 7
AD53XX_READ_AB1 = 0x107 << 7
AD53XX_READ_AB2 = 0x108 << 7
AD53XX_READ_AB3 = 0x109 << 7


@portable
def ad53xx_cmd_write_ch(channel, value, op):
    """Returns the word that must be written to the DAC to set a DAC
    channel register to a given value.

    :param channel: DAC channel to write to (8 bits)
    :param value: 16-bit value to write to the register
    :param op: The channel register to write to, one of
      :const:`AD53XX_CMD_DATA`, :const:`AD53XX_CMD_OFFSET` or
      :const:`AD53XX_CMD_GAIN`.
    :return: The 24-bit word to be written to the DAC
    """
    return op | (channel + 8) << 16 | (value & 0xffff)


@portable
def ad53xx_cmd_read_ch(channel, op):
    """Returns the word that must be written to the DAC to read a given
    DAC channel register.

    :param channel: DAC channel to read (8 bits)
    :param op: The channel register to read, one of
      :const:`AD53XX_READ_X1A`, :const:`AD53XX_READ_X1B`,
      :const:`AD53XX_READ_OFFSET`, :const:`AD53XX_READ_GAIN` etc.
    :return: The 24-bit word to be written to the DAC to initiate read
    """
    return AD53XX_CMD_SPECIAL | AD53XX_SPECIAL_READ | (op + (channel << 7))


@portable
def voltage_to_mu(voltage, offset_dacs=0x2000, vref=5.):
    """Returns the DAC register value required to produce a given output
    voltage, assuming offset and gain errors have been trimmed out.

    Also used to return offset register value required to produce a given
    voltage when the DAC register is set to mid-scale.
    An offset of V can be used to trim out a DAC offset error of -V.

    :param voltage: Voltage
    :param offset_dacs: Register value for the two offset DACs
      (default: 0x2000)
    :param vref: DAC reference voltage (default: 5.)
    """
    return int(round(0x10000*(voltage/(4.*vref)) + offset_dacs*0x4))


class _DummyTTL:
    @portable
    def on(self):
        pass

    @portable
    def off(self):
        pass


class AD53xx:
    """Analog devices AD53[67][0123] family of multi-channel Digital to Analog
    Converters.

    :param spi_device: SPI bus device name
    :param ldac_device: LDAC RTIO TTLOut channel name (optional)
    :param clr_device: CLR RTIO TTLOut channel name (optional)
    :param chip_select: Value to drive on SPI chip select lines during
      transactions (default: 1)
    :param div_write: SPI clock divider for write operations (default: 4,
      50MHz max SPI clock with {t_high, t_low} >=8ns)
    :param div_read: SPI clock divider for read operations (default: 8, not
      optimized for speed, but cf data sheet t22: 25ns min SCLK edge to SDO
      valid)
    :param vref: DAC reference voltage (default: 5.)
    :param offset_dacs: Initial register value for the two offset DACs, device
      dependent and must be set correctly for correct voltage to mu
      conversions. Knowledge of his state is not transferred between
      experiments. (default: 8192)
    :param core_device: Core device name (default: "core")
    """
    kernel_invariants = {"bus", "ldac", "clr", "chip_select", "div_write",
                         "div_read", "vref", "core"}

    def __init__(self, dmgr, spi_device, ldac_device=None, clr_device=None,
                 chip_select=1, div_write=4, div_read=16, vref=5.,
                 offset_dacs=8192, core="core"):
        self.bus = dmgr.get(spi_device)
        self.bus.update_xfer_duration_mu(div_write, 24)
        if ldac_device is None:
            self.ldac = _DummyTTL()
        else:
            self.ldac = dmgr.get(ldac_device)
        if clr_device is None:
            self.clr = _DummyTTL()
        else:
            self.clr = dmgr.get(clr_device)
        self.chip_select = chip_select
        self.div_write = div_write
        self.div_read = div_read
        self.vref = vref
        self.offset_dacs = offset_dacs
        self.core = dmgr.get(core)

    @kernel
    def init(self, blind=False):
        """Configures the SPI bus, drives LDAC and CLR high, programmes
        the offset DACs, and enables overtemperature shutdown.

        This method must be called before any other method at start-up or if
        the SPI bus has been accessed by another device.

        :param blind: If ``True``, do not attempt to read back control register
            or check for overtemperature.
        """
        self.ldac.on()
        self.clr.on()
        self.bus.set_config_mu(SPI_AD53XX_CONFIG, 24, self.div_write,
                               self.chip_select)
        self.write_offset_dacs_mu(self.offset_dacs)
        if not blind:
            ctrl = self.read_reg(channel=0, op=AD53XX_READ_CONTROL)
            if ctrl & 0b10000:
                raise ValueError("DAC over temperature")
            delay(25*us)
        self.bus.write(  # enable power and overtemperature shutdown
            (AD53XX_CMD_SPECIAL | AD53XX_SPECIAL_CONTROL | 0b0010) << 8)
        if not blind:
            ctrl = self.read_reg(channel=0, op=AD53XX_READ_CONTROL)
            if (ctrl & 0b10111) != 0b00010:
                raise ValueError("DAC CONTROL readback mismatch")
            delay(15*us)

    @kernel
    def read_reg(self, channel=0, op=AD53XX_READ_X1A):
        """Read a DAC register.

        This method advances the timeline by the duration of two SPI transfers
        plus two RTIO coarse cycles plus 270 ns and consumes all slack.

        :param channel: Channel number to read from (default: 0)
        :param op: Operation to perform, one of :const:`AD53XX_READ_X1A`,
          :const:`AD53XX_READ_X1B`, :const:`AD53XX_READ_OFFSET`,
          :const:`AD53XX_READ_GAIN` etc. (default: :const:`AD53XX_READ_X1A`).
        :return: The 16 bit register value
        """
        self.bus.write(ad53xx_cmd_read_ch(channel, op) << 8)
        self.bus.set_config_mu(SPI_AD53XX_CONFIG | spi.SPI_INPUT, 24,
                               self.div_read, self.chip_select)
        delay(270*ns)  # t_21 min sync high in readback
        self.bus.write((AD53XX_CMD_SPECIAL | AD53XX_SPECIAL_NOP) << 8)
        self.bus.set_config_mu(SPI_AD53XX_CONFIG, 24, self.div_write,
                               self.chip_select)
        # FIXME: the int32 should not be needed to resolve unification
        return self.bus.read() & int32(0xffff)

    @kernel
    def write_offset_dacs_mu(self, value):
        """Program the OFS0 and OFS1 offset DAC registers.

        Writes to the offset DACs take effect immediately without requiring
        a LDAC. This method advances the timeline by the duration of two SPI
        transfers.

        :param value: Value to set both offset DAC registers to
        """
        value &= 0x3fff
        self.offset_dacs = value
        self.bus.write((AD53XX_CMD_SPECIAL | AD53XX_SPECIAL_OFS0 | value) << 8)
        self.bus.write((AD53XX_CMD_SPECIAL | AD53XX_SPECIAL_OFS1 | value) << 8)

    @kernel
    def write_gain_mu(self, channel, gain=0xffff):
        """Program the gain register for a DAC channel.

        The DAC output is not updated until LDAC is pulsed (see :meth load:).
        This method advances the timeline by the duration of one SPI transfer.

        :param gain: 16-bit gain register value (default: 0xffff)
        """
        self.bus.write(
            ad53xx_cmd_write_ch(channel, gain, AD53XX_CMD_GAIN) << 8)

    @kernel
    def write_offset_mu(self, channel, offset=0x8000):
        """Program the offset register for a DAC channel.

        The DAC output is not updated until LDAC is pulsed (see :meth load:).
        This method advances the timeline by the duration of one SPI transfer.

        :param offset: 16-bit offset register value (default: 0x8000)
        """
        self.bus.write(
            ad53xx_cmd_write_ch(channel, offset, AD53XX_CMD_OFFSET) << 8)

    @kernel
    def write_offset(self, channel, voltage):
        """Program the DAC offset voltage for a channel.

        An offset of +V can be used to trim out a DAC offset error of -V.
        The DAC output is not updated until LDAC is pulsed (see :meth load:).
        This method advances the timeline by the duration of one SPI transfer.

        :param voltage: the offset voltage
        """
        self.write_offset_mu(channel, voltage_to_mu(voltage, self.offset_dacs,
                                                    self.vref))

    @kernel
    def write_dac_mu(self, channel, value):
        """Program the DAC input register for a channel.

        The DAC output is not updated until LDAC is pulsed (see :meth load:).
        This method advances the timeline by the duration of one SPI transfer.
        """
        self.bus.write(
            ad53xx_cmd_write_ch(channel, value, AD53XX_CMD_DATA) << 8)

    @kernel
    def write_dac(self, channel, voltage):
        """Program the DAC output voltage for a channel.

        The DAC output is not updated until LDAC is pulsed (see :meth load:).
        This method advances the timeline by the duration of one SPI transfer.
        """
        self.write_dac_mu(channel, voltage_to_mu(voltage, self.offset_dacs,
                                                 self.vref))

    @kernel
    def load(self):
        """Pulse the LDAC line.

        Note that there is a <= 1.5us "BUSY" period (t10) after writing to a
        DAC input/gain/offset register. All DAC registers may be programmed
        normally during the busy period, however LDACs during the busy period
        cause the DAC output to change *after* the BUSY period has completed,
        instead of the usual immediate update on LDAC behaviour.

        This method advances the timeline by two RTIO clock periods.
        """
        self.ldac.off()
        delay_mu(2*self.bus.ref_period_mu)  # t13 = 10ns ldac pulse width low
        self.ldac.on()

    @kernel
    def set_dac_mu(self, values, channels=list(range(40))):
        """Program multiple DAC channels and pulse LDAC to update the DAC
        outputs.

        This method does not advance the timeline; write events are scheduled
        in the past. The DACs will synchronously start changing their output
        levels `now`.

        If no LDAC device was defined, the LDAC pulse is skipped.

        See :meth load:.

        :param values: list of DAC values to program
        :param channels: list of DAC channels to program. If not specified,
          we program the DAC channels sequentially, starting at 0.
        """
        t0 = now_mu()

        # t10: max busy period after writing to DAC registers
        t_10 = self.core.seconds_to_mu(1500*ns)
        # compensate all delays that will be applied
        delay_mu(-t_10-len(values)*self.bus.xfer_duration_mu)
        for i in range(len(values)):
            self.write_dac_mu(channels[i], values[i])
        delay_mu(t_10)
        self.load()
        at_mu(t0)

    @kernel
    def set_dac(self, voltages, channels=list(range(40))):
        """Program multiple DAC channels and pulse LDAC to update the DAC
        outputs.

        This method does not advance the timeline; write events are scheduled
        in the past. The DACs will synchronously start changing their output
        levels `now`.

        If no LDAC device was defined, the LDAC pulse is skipped.

        :param voltages: list of voltages to program the DAC channels to
        :param channels: list of DAC channels to program. If not specified,
          we program the DAC channels sequentially, starting at 0.
        """
        values = [voltage_to_mu(voltage, self.offset_dacs, self.vref)
                  for voltage in voltages]
        self.set_dac_mu(values, channels)

    @kernel
    def calibrate(self, channel, vzs, vfs):
        """ Two-point calibration of a DAC channel.

        Programs the offset and gain register to trim out DAC errors. Does not
        take effect until LDAC is pulsed (see :meth load:).

        Calibration consists of measuring the DAC output voltage for a channel
        with the DAC set to zero-scale (0x0000) and full-scale (0xffff).

        Note that only negative offsets and full-scale errors (DAC gain too
        high) can be calibrated in this fashion.

        :param channel: The number of the calibrated channel
        :params vzs: Measured voltage with the DAC set to zero-scale (0x0000)
        :params vfs: Measured voltage with the DAC set to full-scale (0xffff)
        """
        offset_err = voltage_to_mu(vzs, self.offset_dacs, self.vref)
        gain_err = voltage_to_mu(vfs, self.offset_dacs, self.vref) - (
            offset_err + 0xffff)

        assert offset_err <= 0
        assert gain_err >= 0

        self.core.break_realtime()
        self.write_offset_mu(channel, 0x8000-offset_err)
        self.write_gain_mu(channel, 0xffff-gain_err)
