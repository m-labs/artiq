from artiq.language.core import kernel, delay_mu, delay, portable
from artiq.language.units import us, ns, ms
from artiq.coredevice.urukul import urukul_sta_pll_lock

from numpy import int32, int64


_AD9910_REG_CFR1 = 0x00
_AD9910_REG_CFR2 = 0x01
_AD9910_REG_CFR3 = 0x02
_AD9910_REG_AUX_DAC = 0x03
_AD9910_REG_IO_UPD = 0x04
_AD9910_REG_FTW = 0x07
_AD9910_REG_POW = 0x08
_AD9910_REG_ASF = 0x09
_AD9910_REG_MSYNC = 0x0A
_AD9910_REG_DRAMPL = 0x0B
_AD9910_REG_DRAMPS = 0x0C
_AD9910_REG_DRAMPR = 0x0D
_AD9910_REG_PR0 = 0x0E
_AD9910_REG_PR1 = 0x0F
_AD9910_REG_PR2 = 0x10
_AD9910_REG_PR3 = 0x11
_AD9910_REG_PR4 = 0x12
_AD9910_REG_PR5 = 0x13
_AD9910_REG_PR6 = 0x14
_AD9910_REG_PR7 = 0x15
_AD9910_REG_RAM = 0x16


class AD9910:
    """
    Support for the AD9910 DDS on Urukul

    :param chip_select: Chip select configuration.
    :param cpld_device: Name of the Urukul CPLD this device is on.
    :param sw_device: Name of the RF switch device.
    """
    kernel_invariants = {"chip_select", "cpld", "core", "bus", "sw",
            "ftw_per_hz", "sysclk", "pll_n", "pll_cp", "pll_vco"}

    def __init__(self, dmgr, chip_select, cpld_device, sw_device=None,
            pll_n=40, pll_cp=7, pll_vco=5):
        self.cpld = dmgr.get(cpld_device)
        self.core = self.cpld.core
        self.bus = self.cpld.bus
        assert 4 <= chip_select <= 7
        self.chip_select = chip_select
        if sw_device:
            self.sw = dmgr.get(sw_device)
        assert 12 <= pll_n <= 127
        self.pll_n = pll_n
        self.sysclk = self.cpld.refclk*pll_n/4  # Urukul clock fanout divider
        self.ftw_per_hz = 1./self.sysclk*(int64(1) << 32)
        assert 0 <= pll_vco <= 5
        vco_min, vco_max = [(370, 510), (420, 590), (500, 700),
                (600, 880), (700, 950), (820, 1150)][pll_vco]
        assert vco_min <= self.sysclk/1e6 <= vco_max
        self.pll_vco = pll_vco
        assert 0 <= pll_cp <= 7
        self.pll_cp = pll_cp

    @kernel
    def write32(self, addr, data):
        self.bus.set_xfer(self.chip_select, 8, 0)
        self.bus.write(addr << 24)
        delay_mu(-self.bus.xfer_period_mu)
        self.bus.set_xfer(self.chip_select, 32, 0)
        self.bus.write(data)
        delay_mu(self.bus.xfer_period_mu - self.bus.write_period_mu)

    @kernel
    def write64(self, addr, data_high, data_low):
        self.bus.set_xfer(self.chip_select, 8, 0)
        self.bus.write(addr << 24)
        t = self.bus.xfer_period_mu
        delay_mu(-t)
        self.bus.set_xfer(self.chip_select, 32, 0)
        self.bus.write(data_high)
        self.bus.write(data_low)
        delay_mu(t - 2*self.bus.write_period_mu)

    @kernel
    def read32(self, addr):
        self.bus.set_xfer(self.chip_select, 8, 0)
        self.bus.write((addr | 0x80) << 24)
        delay_mu(-self.bus.xfer_period_mu)
        self.bus.set_xfer(self.chip_select, 0, 32)
        self.bus.write(0)
        delay_mu(2*self.bus.xfer_period_mu)
        data = self.bus.read_sync()
        return data

    @kernel
    def init(self):
        self.write32(_AD9910_REG_CFR1, 0x00000002)
        delay(100*ns)
        self.cpld.io_update.pulse(100*ns)
        aux_dac = self.read32(_AD9910_REG_AUX_DAC)
        if aux_dac & 0xff != 0x7f:
            raise ValueError("Urukul AD9910 AUX_DAC mismatch")
        delay(10*us)
        self.write32(_AD9910_REG_CFR2, 0x01400020)
        cfr3 = (0x0807c100 | (self.pll_vco << 24) |
                (self.pll_cp << 19) | (self.pll_n << 1))
        self.write32(_AD9910_REG_CFR3, cfr3 | 0x400)  # PFD reset
        delay(10*us)
        self.cpld.io_update.pulse(100*ns)
        self.write32(_AD9910_REG_CFR3, cfr3)
        delay(10*us)
        self.cpld.io_update.pulse(100*ns)
        for i in range(100):
            lock = urukul_sta_pll_lock(self.cpld.sta_read())
            delay(1*ms)
            if lock & (1 << self.chip_select - 4) != 0:
                return
        raise ValueError("PLL failed to lock")

    @kernel
    def set_mu(self, ftw, pow=0, asf=0x3fff):
        self.write64(_AD9910_REG_PR0, (asf << 16) | pow, ftw)
        self.cpld.io_update.pulse(10*ns)

    @portable(flags={"fast-math"})
    def frequency_to_ftw(self, frequency):
        """Returns the frequency tuning word corresponding to the given
        frequency.
        """
        return int32(round(self.ftw_per_hz*frequency))

    @portable(flags={"fast-math"})
    def turns_to_pow(self, turns):
        """Returns the phase offset word corresponding to the given phase
        in turns."""
        return int32(round(turns*0x10000))

    @portable(flags={"fast-math"})
    def amplitude_to_asf(self, amplitude):
        """Returns amplitude scale factor corresponding to given amplitude."""
        return int32(round(amplitude*0x3ffe))

    @kernel
    def set(self, frequency, phase=0.0, amplitude=1.0):
        self.set_mu(self.frequency_to_ftw(frequency),
                    self.turns_to_pow(phase),
                    self.amplitude_to_asf(amplitude))

    @kernel
    def set_att_mu(self, att):
        self.cpld.set_att_mu(self.chip_select - 4, att)

    @kernel
    def set_att(self, att):
        self.cpld.set_att(self.chip_select - 4, att)
