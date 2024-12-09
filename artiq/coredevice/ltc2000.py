from artiq.coredevice.rtio import rtio_output
from artiq.experiment import *
from artiq.coredevice import spi2
from artiq.gateware.targets.ltc2000 import LTC2000DDSModule as DDS
from artiq.language.core import kernel, delay
from artiq.language.units import us

class LTC2000:
    def __init__(self, dmgr, channel, spi_device):
        self.spi = dmgr.get(spi_device)
        self.bus_channel = channel
        self.ftw_per_hz = (2**32) / 2400e6  # Precompute FTW per Hz constant

    @kernel
    def init(self):
        config = (0 * spi2.SPI_OFFLINE |
                  1 * spi2.SPI_END |
                  0 * spi2.SPI_INPUT |
                  0 * spi2.SPI_CS_POLARITY |
                  0 * spi2.SPI_CLK_POLARITY |
                  0 * spi2.SPI_CLK_PHASE |
                  0 * spi2.SPI_LSB_FIRST |
                  0 * spi2.SPI_HALF_DUPLEX)
        self.spi.set_config_mu(config, 16, 32, 1)

    @kernel
    def write(self, addr, data):
        self.spi.write(((addr & 0x7F) << 24) | ((data & 0xFF) << 16))

    @kernel
    def read(self, addr):
        return self.spi.write((1 << 31) | ((addr & 0x7F) << 24)) & 0xFF000000

    @kernel
    def write_rtio(self, csr_address, data):
        address = (self.bus_channel << 8) | csr_address
        rtio_output(address, data)
        delay(1 * us)

    @kernel
    def set_frequency(self, freq):
        ftw = self.frequency_to_ftw(freq)
        self.write_rtio(DDS.FTW_ADDR, ftw)

    @portable
    def frequency_to_ftw(self, freq: float) -> TInt32:
        ftw = int(freq * self.ftw_per_hz)
        return ftw

    @kernel
    def set_ftw(self, ftw):
        self.write_rtio(DDS.FTW_ADDR, ftw)

    @kernel
    def set_amplitude(self, amplitude):
        amp = round(amplitude * 0x3FFF)
        self.write_rtio(DDS.ATW_ADDR, amp)

    @kernel
    def set_phase(self, phase):
        phase_word = round((phase % 360) / 360 * 0xFFFF)
        self.write_rtio(DDS.PTW_ADDR, phase_word)

    @kernel
    def set_clear(self, value: TInt32):
        self.write_rtio(DDS.CLR_ADDR, value)

    @kernel
    def set_reset(self, value: TInt32):
        self.write_rtio(DDS.RST_ADDR, value)

    @kernel
    def reset(self):
        self.set_reset(1)
        delay(10 * us)
        self.set_reset(0)

    @kernel
    def initialize(self):
        self.init()
        self.write(0x01, 0x00)  # Reset, power down controls
        self.write(0x02, 0x00)  # Clock and DCKO controls
        self.write(0x03, 0x01)  # DCKI controls
        self.write(0x04, 0x0B)  # Data input controls
        self.write(0x05, 0x00)  # Synchronizer controls
        self.write(0x07, 0x00)  # Linearization controls
        self.write(0x08, 0x08)  # Linearization voltage controls
        self.write(0x18, 0x00)  # LVDS test MUX controls
        self.write(0x19, 0x00)  # Temperature measurement controls
        self.write(0x1E, 0x00)  # Pattern generator enable
        self.write(0x1F, 0x00)  # Pattern generator data

    @kernel
    def configure(self, frequency, amplitude, phase):
        self.set_frequency(frequency)
        self.set_amplitude(amplitude)
        self.set_phase(phase)
