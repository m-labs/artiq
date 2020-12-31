from artiq.language.core import kernel, delay, portable
from artiq.language.units import ns

from artiq.coredevice import spi2 as spi


SPI_CONFIG = (0*spi.SPI_OFFLINE | 0*spi.SPI_END |
              0*spi.SPI_INPUT | 0*spi.SPI_CS_POLARITY |
              0*spi.SPI_CLK_POLARITY | 0*spi.SPI_CLK_PHASE |
              0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX)


SPI_CS_ADC = 0  # no CS, SPI_END does not matter, framing is done with CNV
SPI_CS_PGIA = 1  # separate SPI bus, CS used as RCLK


@portable
def adc_mu_to_volt(data, gain=0):
    """Convert ADC data in machine units to Volts.

    :param data: 16 bit signed ADC word
    :param gain: PGIA gain setting (0: 1, ..., 3: 1000)
    :return: Voltage in Volts
    """
    if gain == 0:
        volt_per_lsb = 20./(1 << 16)
    elif gain == 1:
        volt_per_lsb = 2./(1 << 16)
    elif gain == 2:
        volt_per_lsb = .2/(1 << 16)
    elif gain == 3:
        volt_per_lsb = .02/(1 << 16)
    else:
        raise ValueError("invalid gain")
    return data*volt_per_lsb


class Sampler:
    """Sampler ADC.

    Controls the LTC2320-16 8 channel 16 bit ADC with SPI interface and
    the switchable gain instrumentation amplifiers.

    :param spi_adc_device: ADC SPI bus device name
    :param spi_pgia_device: PGIA SPI bus device name
    :param cnv_device: CNV RTIO TTLOut channel name
    :param div: SPI clock divider (default: 8)
    :param gains: Initial value for PGIA gains shift register
        (default: 0x0000). Knowledge of this state is not transferred
        between experiments.
    :param core_device: Core device name
    """
    kernel_invariants = {"bus_adc", "bus_pgia", "core", "cnv", "div"}

    def __init__(self, dmgr, spi_adc_device, spi_pgia_device, cnv_device,
                 div=8, gains=0x0000, core_device="core"):
        self.bus_adc = dmgr.get(spi_adc_device)
        self.bus_adc.update_xfer_duration_mu(div, 32)
        self.bus_pgia = dmgr.get(spi_pgia_device)
        self.bus_pgia.update_xfer_duration_mu(div, 16)
        self.core = dmgr.get(core_device)
        self.cnv = dmgr.get(cnv_device)
        self.div = div
        self.gains = gains

    @kernel
    def init(self):
        """Initialize the device.

        Sets up SPI channels.
        """
        self.bus_adc.set_config_mu(SPI_CONFIG | spi.SPI_INPUT | spi.SPI_END,
                                   32, self.div, SPI_CS_ADC)
        self.bus_pgia.set_config_mu(SPI_CONFIG | spi.SPI_END,
                                    16, self.div, SPI_CS_PGIA)

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
        self.bus_pgia.write(gains << 16)
        self.gains = gains

    @kernel
    def get_gains_mu(self):
        """Read the PGIA gain settings of all channels.

        :return: The PGIA gain settings in machine units.
        """
        self.bus_pgia.set_config_mu(SPI_CONFIG | spi.SPI_END | spi.SPI_INPUT,
                                    16, self.div, SPI_CS_PGIA)
        self.bus_pgia.write(self.gains << 16)
        self.bus_pgia.set_config_mu(SPI_CONFIG | spi.SPI_END,
                                    16, self.div, SPI_CS_PGIA)
        self.gains = self.bus_pgia.read() & 0xffff
        return self.gains

    @kernel
    def sample_mu(self, data):
        """Acquire a set of samples.

        Perform a conversion and transfer the samples.

        This assumes that the input FIFO of the ADC SPI RTIO channel is deep
        enough to buffer the samples (half the length of `data` deep).
        If it is not, there will be RTIO input overflows.

        :param data: List of data samples to fill. Must have even length.
            Samples are always read from the last channel (channel 7) down.
            The `data` list will always be filled with the last item
            holding to the sample from channel 7.
        """
        self.cnv.pulse(30*ns)  # t_CNVH
        delay(450*ns)  # t_CONV
        mask = 1 << 15
        for i in range(len(data)//2):
            self.bus_adc.write(0)
        for i in range(len(data) - 1, -1, -2):
            val = self.bus_adc.read()
            data[i] = val >> 16
            val &= 0xffff
            data[i - 1] = -(val & mask) + (val & ~mask)

    @kernel
    def sample(self, data):
        """Acquire a set of samples.

        .. seealso:: :meth:`sample_mu`

        :param data: List of floating point data samples to fill.
        """
        n = len(data)
        adc_data = [0]*n
        self.sample_mu(adc_data)
        for i in range(n):
            channel = i + 8 - len(data)
            gain = (self.gains >> (channel*2)) & 0b11
            data[i] = adc_mu_to_volt(adc_data[i], gain)
