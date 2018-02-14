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
    AD9910 DDS channel on Urukul.

    This class supports a single DDS channel and exposes the DDS,
    the digital step attenuator, and the RF switch.

    :param chip_select: Chip select configuration. On Urukul this is an
        encoded chip select and not "one-hot".
    :param cpld_device: Name of the Urukul CPLD this device is on.
    :param sw_device: Name of the RF switch device. The RF switch is a
        TTLOut channel available as the :attr:`sw` attribute of this instance.
    :param pll_n: DDS PLL multiplier. The DDS sample clock is
        f_ref/4*pll_n where f_ref is the reference frequency (set in the parent
        Urukul CPLD instance).
    :param pll_cp: DDS PLL charge pump setting.
    :param pll_vco: DDS PLL VCO range selection.
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
        assert self.cpld.refclk < 60e6
        self.sysclk = self.cpld.refclk*pll_n/4  # Urukul clock fanout divider
        assert self.sysclk < 1e9
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
        """Write to 32 bit register.

        :param addr: Register address
        :param data: Data to be written
        """
        self.bus.set_xfer(self.chip_select, 8, 0)
        self.bus.write(addr << 24)
        delay_mu(-self.bus.xfer_period_mu + 8)
        self.bus.set_xfer(self.chip_select, 32, 0)
        self.bus.write(data)
        delay_mu(self.bus.xfer_period_mu - self.bus.write_period_mu)

    @kernel
    def write64(self, addr, data_high, data_low):
        """Write to 64 bit register.

        :param addr: Register address
        :param data_high: High (MSB) 32 bits of the data
        :param data_low: Low (LSB) 32 data bits
        """
        self.bus.set_xfer(self.chip_select, 8, 0)
        self.bus.write(addr << 24)
        t = self.bus.xfer_period_mu
        delay_mu(-t + 8)
        self.bus.set_xfer(self.chip_select, 32, 0)
        self.bus.write(data_high)
        self.bus.write(data_low)
        delay_mu(t - 2*self.bus.write_period_mu)

    @kernel
    def read32(self, addr):
        """Read from 32 bit register.

        :param addr: Register address
        """
        self.bus.set_xfer(self.chip_select, 8, 0)
        self.bus.write((addr | 0x80) << 24)
        delay_mu(-self.bus.xfer_period_mu + 8)
        self.bus.set_xfer(self.chip_select, 0, 32)
        self.bus.write(0)
        delay_mu(2*self.bus.xfer_period_mu)
        data = self.bus.read_sync()
        return data

    @kernel
    def init(self):
        """Initialize and configure the DDS."""
        # Set SPI mode
        self.write32(_AD9910_REG_CFR1, 0x00000002)
        delay(100*us)
        self.cpld.io_update.pulse(100*ns)
        # Use the AUX DAC setting to identify and confirm presence
        aux_dac = self.read32(_AD9910_REG_AUX_DAC)
        if aux_dac & 0xff != 0x7f:
            raise ValueError("Urukul AD9910 AUX_DAC mismatch")
        delay(100*us)
        # Configure PLL settings and bring up PLL
        self.write32(_AD9910_REG_CFR2, 0x01400020)
        cfr3 = (0x0807c100 | (self.pll_vco << 24) |
                (self.pll_cp << 19) | (self.pll_n << 1))
        self.write32(_AD9910_REG_CFR3, cfr3 | 0x400)  # PFD reset
        delay(100*us)
        self.cpld.io_update.pulse(100*ns)
        self.write32(_AD9910_REG_CFR3, cfr3)
        delay(100*us)
        self.cpld.io_update.pulse(100*ns)
        # Wait for PLL lock, up to 100 ms
        for i in range(100):
            lock = urukul_sta_pll_lock(self.cpld.sta_read())
            delay(1*ms)
            if lock & (1 << self.chip_select - 4) != 0:
                return
        raise ValueError("PLL failed to lock")

    @kernel
    def set_mu(self, ftw=int32(0), pow=int32(0), asf=int32(0x3fff)):
        """Set profile 0 data in machine units.

        After the SPI transfer, the shared IO update pin is pulsed to
        activate the data.

        :param ftw: Frequency tuning word: 32 bit unsigned.
        :param pow: Phase tuning word: 16 bit unsigned.
        :param asf: Amplitude scale factor: 14 bit unsigned.
        """
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
        """Set profile 0 data in SI units.

        .. seealso:: :meth:`set_mu`

        :param ftw: Frequency in Hz
        :param pow: Phase tuning word in turns
        :param asf: Amplitude in units of full scale
        """
        self.set_mu(self.frequency_to_ftw(frequency),
                    self.turns_to_pow(phase),
                    self.amplitude_to_asf(amplitude))

    @kernel
    def set_att_mu(self, att=int32(0)):
        """Set digital step attenuator in machine units.

        .. seealso:: :meth:`artiq.coredevice.urukul.CPLD.set_att_mu`

        :param att: Attenuation setting, 8 bit digital.
        """
        self.cpld.set_att_mu(self.chip_select - 4, att)

    @kernel
    def set_att(self, att):
        """Set digital step attenuator in SI units.

        .. seealso:: :meth:`artiq.coredevice.urukul.CPLD.set_att`

        :param att: Attenuation in dB.
        """
        self.cpld.set_att(self.chip_select - 4, att)
