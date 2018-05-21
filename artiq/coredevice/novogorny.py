from artiq.language.core import kernel, delay, portable
from artiq.language.units import ns

from artiq.coredevice import spi2 as spi


SPI_CONFIG = (0*spi.SPI_OFFLINE | 0*spi.SPI_END |
              0*spi.SPI_INPUT | 0*spi.SPI_CS_POLARITY |
              0*spi.SPI_CLK_POLARITY | 0*spi.SPI_CLK_PHASE |
              0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX)


SPI_CS_ADC = 1
SPI_CS_SR = 2


@portable
def adc_ctrl(channel=1, softspan=0b111, valid=1):
    """Build a LTC2335-16 control word"""
    return (valid << 7) | (channel << 3) | softspan


@portable
def adc_softspan(data):
    """Return the softspan configuration index from a result packet"""
    return data & 0x7


@portable
def adc_channel(data):
    """Return the channel index from a result packet"""
    return (data >> 3) & 0x7


@portable
def adc_data(data):
    """Return the ADC value from a result packet"""
    return (data >> 8) & 0xffff


@portable
def adc_value(data, v_ref=5.):
    """Convert a ADC result packet to SI units (Volt)"""
    softspan = adc_softspan(data)
    data = adc_data(data)
    g = 625
    if softspan & 4:
        g *= 2
    if softspan & 2:
        h = 1 << 15
    else:
        h = 1 << 16
    data = -(data & h) + (data & ~h)
    if softspan & 1:
        h *= 500
    else:
        h *= 512
    v_per_lsb = v_ref*g/h
    return data*v_per_lsb


class Novogorny:
    """Novogorny ADC.

    Controls the LTC2335-16 8 channel ADC with SPI interface and
    the switchable gain instrumentation amplifiers using a shift
    register.

    :param spi_device: SPI bus device name
    :param cnv_device: CNV RTIO TTLOut channel name
    :param div: SPI clock divider (default: 8)
    :param gains: Initial value for PGIA gains shift register
        (default: 0x0000). Knowledge of this state is not transferred
        between experiments.
    :param core_device: Core device name
    """
    kernel_invariants = {"bus", "core", "cnv", "div", "v_ref"}

    def __init__(self, dmgr, spi_device, cnv_device, div=8, gains=0x0000,
                 core_device="core"):
        self.bus = dmgr.get(spi_device)
        self.core = dmgr.get(core_device)
        self.cnv = dmgr.get(cnv_device)
        self.div = div
        self.gains = gains
        self.v_ref = 5.  # 5 Volt reference

    @kernel
    def set_gain_mu(self, channel, gain):
        """Set instrumentation amplifier gain of a channel.

        The four gain settings (0, 1, 2, 3) corresponds to gains of
        (1, 10, 100, 1000) respectively.

        :param channel: Channel index
        :param gain: Gain setting
        """
        gains = self.gains
        gains &= ~(0b11 << (channel*2))
        gains |= gain << (channel*2)
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END,
                               16, self.div, SPI_CS_SR)
        self.bus.write(gains << 16)
        self.gains = gains

    @kernel
    def configure(self, data):
        """Set up the ADC sequencer.

        :param data: List of 8 bit control words to write into the sequencer
            table.
        """
        if len(data) > 1:
            self.bus.set_config_mu(SPI_CONFIG,
                                   8, self.div, SPI_CS_ADC)
            for i in range(len(data) - 1):
                self.bus.write(data[i] << 24)
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END,
                               8, self.div, SPI_CS_ADC)
        self.bus.write(data[len(data) - 1] << 24)

    @kernel
    def sample_mu(self, next_ctrl=0):
        """Acquire a sample:

        Perform a conversion and transfer the sample.

        :param next_ctrl: ADC control word for the next sample
        :return: The ADC result packet (machine units)
        """
        self.cnv.pulse(40*ns)  # t_CNVH
        delay(560*ns)  # t_CONV max
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_INPUT | spi.SPI_END,
                               24, self.div, SPI_CS_ADC)
        self.bus.write(next_ctrl << 24)
        return self.bus.read()

    @kernel
    def sample(self, next_ctrl=0):
        """Acquire a sample

        .. seealso:: :meth:`sample_mu`

        :param next_ctrl: ADC control word for the next sample
        :return: The ADC result packet (Volt)
        """
        return adc_value(self.sample_mu(), self.v_ref)

    @kernel
    def burst_mu(self, data, dt_mu, ctrl=0):
        """Acquire a burst of samples.

        If the burst is too long and the sample rate too high, there will be
        RTIO input overflows.

        High sample rates lead to gain errors since the impedance between the
        instrumentation amplifier and the ADC is high.

        :param data: List of data values to write result packets into.
            In machine units.
        :param dt: Sample interval in machine units.
        :param ctrl: ADC control word to write during each result packet
            transfer.
        """
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_INPUT | spi.SPI_END,
                               24, self.div, SPI_CS_ADC)
        for i in range(len(data)):
            t0 = now_mu()
            self.cnv.pulse(40*ns)  # t_CNVH
            delay(560*ns)  # t_CONV max
            self.bus.write(ctrl << 24)
            at_mu(t0 + dt_mu)
        for i in range(len(data)):
            data[i] = self.bus.read()
