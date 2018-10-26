from numpy import int32, int64

from artiq.language.core import kernel, delay, portable
from artiq.language.units import us, ns, ms

from artiq.coredevice import spi2 as spi
from artiq.coredevice import urukul
urukul_sta_pll_lock = urukul.urukul_sta_pll_lock
urukul_sta_smp_err = urukul.urukul_sta_smp_err


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
        encoded chip select and not "one-hot": 3 to address multiple chips
        (as configured through CFG_MASK_NU), 4-7 for individual channels.
    :param cpld_device: Name of the Urukul CPLD this device is on.
    :param sw_device: Name of the RF switch device. The RF switch is a
        TTLOut channel available as the :attr:`sw` attribute of this instance.
    :param pll_n: DDS PLL multiplier. The DDS sample clock is
        f_ref/4*pll_n where f_ref is the reference frequency (set in the parent
        Urukul CPLD instance).
    :param pll_cp: DDS PLL charge pump setting.
    :param pll_vco: DDS PLL VCO range selection.
    :param sync_delay_seed: SYNC_IN delay tuning starting value.
        To stabilize the SYNC_IN delay tuning, run :meth:`tune_sync_delay` once and
        set this to the delay tap number returned by :meth:`tune_sync_delay`.
    """
    kernel_invariants = {"chip_select", "cpld", "core", "bus",
            "ftw_per_hz", "pll_n", "pll_cp", "pll_vco", "sync_delay_seed"}

    def __init__(self, dmgr, chip_select, cpld_device, sw_device=None,
            pll_n=40, pll_cp=7, pll_vco=5, sync_delay_seed=8):
        self.cpld = dmgr.get(cpld_device)
        self.core = self.cpld.core
        self.bus = self.cpld.bus
        assert 3 <= chip_select <= 7
        self.chip_select = chip_select
        if sw_device:
            self.sw = dmgr.get(sw_device)
            self.kernel_invariants.add("sw")
        assert 12 <= pll_n <= 127
        self.pll_n = pll_n
        assert self.cpld.refclk/4 <= 60e6
        sysclk = self.cpld.refclk*pll_n/4  # Urukul clock fanout divider
        assert sysclk <= 1e9
        self.ftw_per_hz = 1./sysclk*(int64(1) << 32)
        assert 0 <= pll_vco <= 5
        vco_min, vco_max = [(370, 510), (420, 590), (500, 700),
                (600, 880), (700, 950), (820, 1150)][pll_vco]
        assert vco_min <= sysclk/1e6 <= vco_max
        self.pll_vco = pll_vco
        assert 0 <= pll_cp <= 7
        self.pll_cp = pll_cp
        self.sync_delay_seed = sync_delay_seed

    @kernel
    def write32(self, addr, data):
        """Write to 32 bit register.

        :param addr: Register address
        :param data: Data to be written
        """
        self.bus.set_config_mu(urukul.SPI_CONFIG, 8,
                urukul.SPIT_DDS_WR, self.chip_select)
        self.bus.write(addr << 24)
        self.bus.set_config_mu(urukul.SPI_CONFIG | spi.SPI_END, 32,
                urukul.SPIT_DDS_WR, self.chip_select)
        self.bus.write(data)

    @kernel
    def read32(self, addr):
        """Read from 32 bit register.

        :param addr: Register address
        """
        self.bus.set_config_mu(urukul.SPI_CONFIG, 8,
                urukul.SPIT_DDS_WR, self.chip_select)
        self.bus.write((addr | 0x80) << 24)
        self.bus.set_config_mu(urukul.SPI_CONFIG | spi.SPI_END
                | spi.SPI_INPUT, 32,
                urukul.SPIT_DDS_RD, self.chip_select)
        self.bus.write(0)
        return self.bus.read()

    @kernel
    def write64(self, addr, data_high, data_low):
        """Write to 64 bit register.

        :param addr: Register address
        :param data_high: High (MSB) 32 bits of the data
        :param data_low: Low (LSB) 32 data bits
        """
        self.bus.set_config_mu(urukul.SPI_CONFIG, 8,
                urukul.SPIT_DDS_WR, self.chip_select)
        self.bus.write(addr << 24)
        self.bus.set_config_mu(urukul.SPI_CONFIG, 32,
                urukul.SPIT_DDS_WR, self.chip_select)
        self.bus.write(data_high)
        self.bus.set_config_mu(urukul.SPI_CONFIG | spi.SPI_END, 32,
                urukul.SPIT_DDS_WR, self.chip_select)
        self.bus.write(data_low)

    @kernel
    def init(self, blind=False):
        """Initialize and configure the DDS.

        Sets up SPI mode, confirms chip presence, powers down unused blocks,
        configures the PLL, waits for PLL lock. Uses the
        IO_UPDATE signal multiple times.

        :param blind: Do not read back DDS identity and do not wait for lock.
        """
        # Set SPI mode
        self.write32(_AD9910_REG_CFR1, 0x00000002)
        self.cpld.io_update.pulse(1*us)
        delay(1*ms)
        if not blind:
            # Use the AUX DAC setting to identify and confirm presence
            aux_dac = self.read32(_AD9910_REG_AUX_DAC)
            if aux_dac & 0xff != 0x7f:
                raise ValueError("Urukul AD9910 AUX_DAC mismatch")
            delay(50*us)  # slack
        # Configure PLL settings and bring up PLL
        self.write32(_AD9910_REG_CFR2, 0x01000020)
        self.cpld.io_update.pulse(1*us)
        cfr3 = (0x0807c100 | (self.pll_vco << 24) |
                (self.pll_cp << 19) | (self.pll_n << 1))
        self.write32(_AD9910_REG_CFR3, cfr3 | 0x400)  # PFD reset
        self.cpld.io_update.pulse(1*us)
        self.write32(_AD9910_REG_CFR3, cfr3)
        self.cpld.io_update.pulse(1*us)
        if blind:
            delay(100*ms)
            return
        # Wait for PLL lock, up to 100 ms
        for i in range(100):
            sta = self.cpld.sta_read()
            lock = urukul_sta_pll_lock(sta)
            delay(1*ms)
            if lock & (1 << self.chip_select - 4):
                return
        raise ValueError("PLL lock timeout")

    @kernel
    def power_down(self, bits=0b1111):
        """Power down DDS.

        :param bits: power down bits, see datasheet
        """
        self.write32(_AD9910_REG_CFR1, 0x00000002 | (bits << 4))
        self.cpld.io_update.pulse(1*us)

    @kernel
    def set_mu(self, ftw, pow=0, asf=0x3fff):
        """Set profile 0 data in machine units.

        After the SPI transfer, the shared IO update pin is pulsed to
        activate the data.

        :param ftw: Frequency tuning word: 32 bit.
        :param pow: Phase tuning word: 16 bit unsigned.
        :param asf: Amplitude scale factor: 14 bit unsigned.
        """
        self.write64(_AD9910_REG_PR0, (asf << 16) | pow, ftw)
        self.cpld.io_update.pulse_mu(8)

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
    def set_att_mu(self, att):
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

    @kernel
    def cfg_sw(self, state):
        """Set CPLD CFG RF switch state. The RF switch is controlled by the
        logical or of the CPLD configuration shift register
        RF switch bit and the SW TTL line (if used).

        :param state: CPLD CFG RF switch bit
        """
        self.cpld.cfg_sw(self.chip_select - 4, state)

    @kernel
    def set_sync(self, in_delay, window, preset=0):
        self.write32(_AD9910_REG_MSYNC,
                     (window << 28) |  # SYNC S/H validation delay
                     (1 << 27) |  # SYNC receiver enable
                     (0 << 26) |  # SYNC generator disable
                     (0 << 25) |  # SYNC generator SYS rising edge
                     (preset << 18) |  # SYNC preset
                     (0 << 11) |  # SYNC output delay
                     (in_delay << 3))  # SYNC receiver delay
        self.write32(_AD9910_REG_CFR2, 0x01000020)  # clear SMP_ERR
        self.cpld.io_update.pulse(1*us)
        self.write32(_AD9910_REG_CFR2, 0x01000000)  # enable SMP_ERR
        self.cpld.io_update.pulse(1*us)

    @kernel
    def tune_sync_delay(self):
        dt = 14  # 1/(f_SYSCLK*75ps)  taps per SYSCLK period
        max_delay = dt  # 14*75ps > 1ns
        max_window = dt//4 + 1  # 2*75ps*4 = 600ps high > 1ns/2
        min_window = dt//8 + 1  # 2*75ps hold, 2*75ps setup < 1ns/4
        for window in range(max_window - min_window + 1):
            window = max_window - window
            for in_delay in range(max_delay):
                # alternate search direction around seed_delay
                if in_delay & 1:
                    in_delay = -in_delay
                in_delay = (self.sync_delay_seed + (in_delay >> 1)) & 0x1f
                self.set_sync(in_delay, window)
                # integrate SMP_ERR statistics for a few hundred cycles
                delay(10*us)
                err = urukul_sta_smp_err(self.cpld.sta_read())
                err = (err >> (self.chip_select - 4)) & 1
                delay(40*us)  # slack
                if not err:
                    window -= min_window  # add margin
                    self.set_sync(in_delay, window)
                    return window, in_delay
        raise ValueError("no valid window/delay")
