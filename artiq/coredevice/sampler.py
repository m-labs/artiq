from numpy import int32

from artiq.language.core import nac3, kernel, portable, Kernel, KernelInvariant
from artiq.language.units import ns

from artiq.coredevice.core import Core
from artiq.coredevice.spi2 import *
from artiq.coredevice.ttl import TTLOut


SPI_CONFIG = (0*SPI_OFFLINE | 0*SPI_END |
              0*SPI_INPUT | 0*SPI_CS_POLARITY |
              0*SPI_CLK_POLARITY | 0*SPI_CLK_PHASE |
              0*SPI_LSB_FIRST | 0*SPI_HALF_DUPLEX)


SPI_CS_ADC = 0  # no CS, SPI_END does not matter, framing is done with CNV
SPI_CS_PGIA = 1  # separate SPI bus, CS used as RCLK


@portable
def adc_mu_to_volt(data: int32, gain: int32 = 0, corrected_fs: bool = True) -> float:
    """Convert ADC data in machine units to Volts.

    :param data: 16 bit signed ADC word
    :param gain: PGIA gain setting (0: 1, ..., 3: 1000)
    :param corrected_fs: use corrected ADC FS reference.
    Should be True for Samplers' revisions after v2.1. False for v2.1 and earlier.
    :return: Voltage in Volts
    """
    volt_per_lsb = 0.
    if gain == 0:
        volt_per_lsb = 20.48 / float(1 << 16) if corrected_fs else 20. / float(1 << 16)
    elif gain == 1:
        volt_per_lsb = 2.048 / float(1 << 16) if corrected_fs else 2. / float(1 << 16)
    elif gain == 2:
        volt_per_lsb = .2048 / float(1 << 16) if corrected_fs else .2 / float(1 << 16)
    elif gain == 3:
        volt_per_lsb = 0.02048 / float(1 << 16) if corrected_fs else .02 / float(1 << 16)
    else:
        raise ValueError("invalid gain")
    return float(data)* volt_per_lsb


@nac3
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
    :param hw_rev: Sampler's hardware revision string (default 'v2.2')
    :param core_device: Core device name
    """
    core: KernelInvariant[Core]
    bus_adc: KernelInvariant[SPIMaster]
    bus_pgia: KernelInvariant[SPIMaster]
    cnv: KernelInvariant[TTLOut]
    div: KernelInvariant[int32]
    gains: Kernel[int32]
    corrected_fs: KernelInvariant[bool]

    def __init__(self, dmgr, spi_adc_device, spi_pgia_device, cnv_device,
                 div=8, gains=0x0000, hw_rev="v2.2", core_device="core"):
        self.bus_adc = dmgr.get(spi_adc_device)
        self.bus_adc.update_xfer_duration_mu(div, 32)
        self.bus_pgia = dmgr.get(spi_pgia_device)
        self.bus_pgia.update_xfer_duration_mu(div, 16)
        self.core = dmgr.get(core_device)
        self.cnv = dmgr.get(cnv_device)
        self.div = div
        self.gains = gains
        self.corrected_fs = self.use_corrected_fs(hw_rev)

    @staticmethod
    def use_corrected_fs(hw_rev):
        return hw_rev != "v2.1"

    @kernel
    def init(self):
        """Initialize the device.

        Sets up SPI channels.
        """
        self.bus_adc.set_config_mu(SPI_CONFIG | SPI_INPUT | SPI_END,
                                   32, self.div, SPI_CS_ADC)
        self.bus_pgia.set_config_mu(SPI_CONFIG | SPI_END,
                                    16, self.div, SPI_CS_PGIA)

    @kernel
    def set_gain_mu(self, channel: int32, gain: int32):
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
    def get_gains_mu(self) -> int32:
        """Read the PGIA gain settings of all channels.

        :return: The PGIA gain settings in machine units.
        """
        self.bus_pgia.set_config_mu(SPI_CONFIG | SPI_END | SPI_INPUT,
                                    16, self.div, SPI_CS_PGIA)
        self.bus_pgia.write(self.gains << 16)
        self.bus_pgia.set_config_mu(SPI_CONFIG | SPI_END,
                                    16, self.div, SPI_CS_PGIA)
        self.gains = self.bus_pgia.read() & 0xffff
        return self.gains

    @kernel
    def sample_mu(self, data: list[int32]):
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
        self.cnv.pulse(30.*ns)  # t_CNVH
        self.core.delay(450.*ns)  # t_CONV
        mask = 1 << 15
        for i in range(len(data)//2):
            self.bus_adc.write(0)
        for i in range(len(data) - 1, -1, -2):
            val = self.bus_adc.read()
            data[i] = val >> 16
            val &= 0xffff
            data[i - 1] = -(val & mask) + (val & ~mask)

    @kernel
    def sample(self, data: list[float]):
        """Acquire a set of samples.

        .. seealso:: :meth:`sample_mu`

        :param data: List of floating point data samples to fill.
        """
        n = len(data)
        adc_data = [0 for _ in range(n)]
        self.sample_mu(adc_data)
        for i in range(n):
            channel = i + 8 - len(data)
            gain = (self.gains >> (channel*2)) & 0b11
            data[i] = adc_mu_to_volt(adc_data[i], gain, self.revision)
