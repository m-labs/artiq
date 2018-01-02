"""
Driver for the AD9912 DDS.
"""


from artiq.language.core import kernel, delay_mu, delay
from artiq.language.units import us, ns
from artiq.coredevice import spi, urukul
from artiq.coredevice.ad9912_reg import *

from numpy import int32, int64


class AD9912:
    """
    Support for the Analog devices AD9912 DDS

    :param chip_select: Chip select configuration.
    :param cpld_device: Name of the Urukul CPLD this device is on.
    :param sw_device: Name of the RF switch device.
    """
    kernel_invariants = {"chip_select", "cpld", "core", "bus", "sw",
            "ftw_per_hz", "sysclk", "pll_n"}

    def __init__(self, dmgr, chip_select, cpld_device, sw_device=None,
            pll_n=10):
        self.cpld = dmgr.get(cpld_device)
        self.core = self.cpld.core
        self.bus = self.cpld.bus
        assert chip_select >= 4
        self.chip_select = chip_select
        if sw_device:
            self.sw = dmgr.get(sw_device)
        self.pll_n = pll_n
        self.sysclk = self.cpld.refclk * pll_n
        self.ftw_per_hz = 1/self.sysclk*(int64(1) << 48)

    @kernel
    def write(self, addr, data, length=1):
        assert length > 0
        assert length <= 4
        self.bus.set_xfer(self.chip_select, 16, 0)
        self.bus.write((addr | ((length - 1) << 13)) << 16)
        delay_mu(-self.bus.xfer_period_mu)
        self.bus.set_xfer(self.chip_select, length*8, 0)
        if length < 4:
            data <<= 32 - length*8
        self.bus.write(data)
        delay_mu(self.bus.xfer_period_mu - self.bus.write_period_mu)

    @kernel
    def read(self, addr, length=1):
        assert length > 0
        assert length <= 4
        self.bus.set_xfer(self.chip_select, 16, 0)
        self.bus.write((addr | ((length - 1) << 13) | 0x8000) << 16)
        delay_mu(-self.bus.xfer_period_mu)
        self.bus.set_xfer(self.chip_select, 0, length*8)
        self.bus.write(0)
        delay_mu(2*self.bus.xfer_period_mu)
        data = self.bus.read_sync()
        if length < 4:
            data &= (1 << (length*8)) - 1
        return data

    @kernel
    def init(self):
        t = now_mu()
        self.write(AD9912_SER_CONF, 0x99)
        prodid = self.read(AD9912_PRODIDH, length=2)
        assert (prodid == 0x1982) or (prodid == 0x1902)
        delay(10*us)
        self.write(AD9912_PWRCNTRL1, 0x80)  # HSTL, CMOS power down
        delay(10*us)
        self.write(AD9912_N_DIV, self.pll_n//2 - 2)
        delay(10*us)
        self.write(AD9912_PLLCFG, 0b00000101)  # 375 µA, high range
        at_mu(t)
        delay(100*us)

    @kernel
    def set_att_mu(self, att):
        self.cpld.set_att_mu(self.chip_select - 4, att)

    @kernel
    def set_att(self, att):
        self.cpld.set_att(self.chip_select - 4, att)

    @kernel
    def set_mu(self, ftw=int64(0), pow=int32(0)):
        # do a streaming transfer of FTW and POW
        self.bus.set_xfer(self.chip_select, 16, 0)
        self.bus.write((AD9912_POW1 << 16) | (3 << 29))
        delay_mu(-self.bus.xfer_period_mu)
        self.bus.set_xfer(self.chip_select, 32, 0)
        self.bus.write((pow << 16) | int32(ftw >> 32))
        self.bus.write(int32(ftw))
        delay_mu(self.bus.xfer_period_mu - self.bus.write_period_mu)
        self.cpld.io_update.pulse(10*ns)

    @portable(flags={"fast-math"})
    def frequency_to_ftw(self, frequency):
        """Returns the frequency tuning word corresponding to the given
        frequency.
        """
        return int64(round(self.ftw_per_hz*frequency))

    @portable(flags={"fast-math"})
    def turns_to_pow(self, phase):
        """Returns the phase offset word corresponding to the given
        phase.
        """
        return int32(round((1 << 16)*phase))

    @kernel
    def set(self, frequency, phase=0.0):
        self.set_mu(self.frequency_to_ftw(frequency),
            self.turns_to_pow(phase))
