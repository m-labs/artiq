from numpy import int32, int64

from artiq.language.core import kernel, delay, portable
from artiq.language.units import ms, us, ns
from artiq.coredevice.ad9912_reg import *

from artiq.coredevice import spi2 as spi
from artiq.coredevice import urukul


class AD9912:
    """
    AD9912 DDS channel on Urukul

    This class supports a single DDS channel and exposes the DDS,
    the digital step attenuator, and the RF switch.

    :param chip_select: Chip select configuration. On Urukul this is an
        encoded chip select and not "one-hot".
    :param cpld_device: Name of the Urukul CPLD this device is on.
    :param sw_device: Name of the RF switch device. The RF switch is a
        TTLOut channel available as the :attr:`sw` attribute of this instance.
    :param pll_n: DDS PLL multiplier. The DDS sample clock is
        f_ref/clk_div*pll_n where f_ref is the reference frequency and clk_div
        is the reference clock divider (both set in the parent Urukul CPLD
        instance).
    """
    kernel_invariants = {"chip_select", "cpld", "core", "bus", "ftw_per_hz"}

    def __init__(self, dmgr, chip_select, cpld_device, sw_device=None,
                 pll_n=10):
        self.cpld = dmgr.get(cpld_device)
        self.core = self.cpld.core
        self.bus = self.cpld.bus
        assert 4 <= chip_select <= 7
        self.chip_select = chip_select
        if sw_device:
            self.sw = dmgr.get(sw_device)
            self.kernel_invariants.add("sw")
        self.pll_n = pll_n
        sysclk = self.cpld.refclk/[1, 1, 2, 4][self.cpld.clk_div]*pll_n
        assert sysclk <= 1e9
        self.ftw_per_hz = 1/sysclk*(int64(1) << 48)

    @kernel
    def write(self, addr, data, length):
        """Variable length write to a register.
        Up to 4 bytes.

        :param addr: Register address
        :param data: Data to be written: int32
        :param length: Length in bytes (1-4)
        """
        assert length > 0
        assert length <= 4
        self.bus.set_config_mu(urukul.SPI_CONFIG, 16,
                urukul.SPIT_DDS_WR, self.chip_select)
        self.bus.write((addr | ((length - 1) << 13)) << 16)
        self.bus.set_config_mu(urukul.SPI_CONFIG | spi.SPI_END, length*8,
                urukul.SPIT_DDS_WR, self.chip_select)
        self.bus.write(data << (32 - length*8))

    @kernel
    def read(self, addr, length):
        """Variable length read from a register.
        Up to 4 bytes.

        :param addr: Register address
        :param length: Length in bytes (1-4)
        :return: Data read
        """
        assert length > 0
        assert length <= 4
        self.bus.set_config_mu(urukul.SPI_CONFIG, 16,
                urukul.SPIT_DDS_WR, self.chip_select)
        self.bus.write((addr | ((length - 1) << 13) | 0x8000) << 16)
        self.bus.set_config_mu(urukul.SPI_CONFIG | spi.SPI_END
                | spi.SPI_INPUT, length*8,
                urukul.SPIT_DDS_RD, self.chip_select)
        self.bus.write(0)
        data = self.bus.read()
        if length < 4:
            data &= (1 << (length*8)) - 1
        return data

    @kernel
    def init(self):
        """Initialize and configure the DDS.

        Sets up SPI mode, confirms chip presence, powers down unused blocks,
        and configures the PLL. Does not wait for PLL lock. Uses the
        IO_UPDATE signal multiple times.
        """
        # SPI mode
        self.write(AD9912_SER_CONF, 0x99, length=1)
        self.cpld.io_update.pulse(2*us)
        # Verify chip ID and presence
        prodid = self.read(AD9912_PRODIDH, length=2)
        if (prodid != 0x1982) and (prodid != 0x1902):
            raise ValueError("Urukul AD9912 product id mismatch")
        delay(50*us)
        # HSTL power down, CMOS power down
        self.write(AD9912_PWRCNTRL1, 0x80, length=1)
        self.cpld.io_update.pulse(2*us)
        self.write(AD9912_N_DIV, self.pll_n//2 - 2, length=1)
        self.cpld.io_update.pulse(2*us)
        # I_cp = 375 µA, VCO high range
        self.write(AD9912_PLLCFG, 0b00000101, length=1)
        self.cpld.io_update.pulse(2*us)
        delay(1*ms)

    @kernel
    def set_att_mu(self, att):
        """Set digital step attenuator in machine units.

        This method will write the attenuator settings of all four channels.

        .. seealso:: :meth:`artiq.coredevice.urukul.CPLD.set_att_mu`

        :param att: Attenuation setting, 8 bit digital.
        """
        self.cpld.set_att_mu(self.chip_select - 4, att)

    @kernel
    def set_att(self, att):
        """Set digital step attenuator in SI units.

        This method will write the attenuator settings of all four channels.

        .. seealso:: :meth:`artiq.coredevice.urukul.CPLD.set_att`

        :param att: Attenuation in dB. Higher values mean more attenuation.
        """
        self.cpld.set_att(self.chip_select - 4, att)

    @kernel
    def set_mu(self, ftw, pow):
        """Set profile 0 data in machine units.

        After the SPI transfer, the shared IO update pin is pulsed to
        activate the data.

        :param ftw: Frequency tuning word: 32 bit unsigned.
        :param pow: Phase tuning word: 16 bit unsigned.
        """
        # streaming transfer of FTW and POW
        self.bus.set_config_mu(urukul.SPI_CONFIG, 16,
                urukul.SPIT_DDS_WR, self.chip_select)
        self.bus.write((AD9912_POW1 << 16) | (3 << 29))
        self.bus.set_config_mu(urukul.SPI_CONFIG, 32,
                urukul.SPIT_DDS_WR, self.chip_select)
        self.bus.write((pow << 16) | (int32(ftw >> 32) & 0xffff))
        self.bus.set_config_mu(urukul.SPI_CONFIG | spi.SPI_END, 32,
                urukul.SPIT_DDS_WR, self.chip_select)
        self.bus.write(int32(ftw))
        self.cpld.io_update.pulse(10*ns)

    @portable(flags={"fast-math"})
    def frequency_to_ftw(self, frequency):
        """Returns the frequency tuning word corresponding to the given
        frequency.
        """
        return int64(round(self.ftw_per_hz*frequency))

    @portable(flags={"fast-math"})
    def ftw_to_frequency(self, ftw):
        """Returns the frequency corresponding to the given
        frequency tuning word.
        """
        return ftw/self.ftw_per_hz

    @portable(flags={"fast-math"})
    def turns_to_pow(self, phase):
        """Returns the phase offset word corresponding to the given
        phase.
        """
        return int32(round((1 << 14)*phase))

    @kernel
    def set(self, frequency, phase=0.0):
        """Set profile 0 data in SI units.

        .. seealso:: :meth:`set_mu`

        :param ftw: Frequency in Hz
        :param pow: Phase tuning word in turns
        """
        self.set_mu(self.frequency_to_ftw(frequency),
            self.turns_to_pow(phase))

    @kernel
    def cfg_sw(self, state):
        """Set CPLD CFG RF switch state. The RF switch is controlled by the
        logical or of the CPLD configuration shift register
        RF switch bit and the SW TTL line (if used).

        :param state: CPLD CFG RF switch bit
        """
        self.cpld.cfg_sw(self.chip_select - 4, state)
