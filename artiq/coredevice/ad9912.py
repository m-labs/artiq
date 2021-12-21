from numpy import int32, int64

from artiq.language.types import TInt32, TInt64, TFloat, TTuple, TBool
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

    def __init__(self, dmgr, chip_select, cpld_device, sw_device=None,
                 pll_n=10):
        self.kernel_invariants = {"cpld", "core", "bus", "chip_select",
                                  "pll_n", "ftw_per_hz"}
        self.cpld = dmgr.get(cpld_device)
        self.core = self.cpld.core
        self.bus = self.cpld.bus
        assert 4 <= chip_select <= 7
        self.chip_select = chip_select
        if sw_device:
            self.sw = dmgr.get(sw_device)
            self.kernel_invariants.add("sw")
        self.pll_n = pll_n
        sysclk = self.cpld.refclk / [1, 1, 2, 4][self.cpld.clk_div] * pll_n
        assert sysclk <= 1e9
        self.ftw_per_hz = 1 / sysclk * (int64(1) << 48)

    @kernel
    def write(self, addr: TInt32, data: TInt32, length: TInt32):
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
        self.bus.set_config_mu(urukul.SPI_CONFIG | spi.SPI_END, length * 8,
                               urukul.SPIT_DDS_WR, self.chip_select)
        self.bus.write(data << (32 - length * 8))

    @kernel
    def read(self, addr: TInt32, length: TInt32) -> TInt32:
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
                               | spi.SPI_INPUT, length * 8,
                               urukul.SPIT_DDS_RD, self.chip_select)
        self.bus.write(0)
        data = self.bus.read()
        if length < 4:
            data &= (1 << (length * 8)) - 1
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
        self.cpld.io_update.pulse(2 * us)
        # Verify chip ID and presence
        prodid = self.read(AD9912_PRODIDH, length=2)
        if (prodid != 0x1982) and (prodid != 0x1902):
            raise ValueError("Urukul AD9912 product id mismatch")
        delay(50 * us)
        # HSTL power down, CMOS power down
        self.write(AD9912_PWRCNTRL1, 0x80, length=1)
        self.cpld.io_update.pulse(2 * us)
        self.write(AD9912_N_DIV, self.pll_n // 2 - 2, length=1)
        self.cpld.io_update.pulse(2 * us)
        # I_cp = 375 µA, VCO high range
        self.write(AD9912_PLLCFG, 0b00000101, length=1)
        self.cpld.io_update.pulse(2 * us)
        delay(1 * ms)

    @kernel
    def set_att_mu(self, att: TInt32):
        """Set digital step attenuator in machine units.

        This method will write the attenuator settings of all four channels.

        .. seealso:: :meth:`artiq.coredevice.urukul.CPLD.set_att_mu`

        :param att: Attenuation setting, 8 bit digital.
        """
        self.cpld.set_att_mu(self.chip_select - 4, att)

    @kernel
    def set_att(self, att: TFloat):
        """Set digital step attenuator in SI units.

        This method will write the attenuator settings of all four channels.

        .. seealso:: :meth:`artiq.coredevice.urukul.CPLD.set_att`

        :param att: Attenuation in dB. Higher values mean more attenuation.
        """
        self.cpld.set_att(self.chip_select - 4, att)

    @kernel
    def get_att_mu(self) -> TInt32:
        """Get digital step attenuator value in machine units.

        .. seealso:: :meth:`artiq.coredevice.urukul.CPLD.get_channel_att_mu`

        :return: Attenuation setting, 8 bit digital.
        """
        return self.cpld.get_channel_att_mu(self.chip_select - 4)

    @kernel
    def get_att(self) -> TFloat:
        """Get digital step attenuator value in SI units.

        .. seealso:: :meth:`artiq.coredevice.urukul.CPLD.get_channel_att`

        :return: Attenuation in dB.
        """
        return self.cpld.get_channel_att(self.chip_select - 4)

    @kernel
    def set_mu(self, ftw: TInt64, pow_: TInt32 = 0):
        """Set profile 0 data in machine units.

        After the SPI transfer, the shared IO update pin is pulsed to
        activate the data.

        :param ftw: Frequency tuning word: 48 bit unsigned.
        :param pow_: Phase tuning word: 16 bit unsigned.
        """
        # streaming transfer of FTW and POW
        self.bus.set_config_mu(urukul.SPI_CONFIG, 16,
                               urukul.SPIT_DDS_WR, self.chip_select)
        self.bus.write((AD9912_POW1 << 16) | (3 << 29))
        self.bus.set_config_mu(urukul.SPI_CONFIG, 32,
                               urukul.SPIT_DDS_WR, self.chip_select)
        self.bus.write((pow_ << 16) | (int32(ftw >> 32) & 0xffff))
        self.bus.set_config_mu(urukul.SPI_CONFIG | spi.SPI_END, 32,
                               urukul.SPIT_DDS_WR, self.chip_select)
        self.bus.write(int32(ftw))
        self.cpld.io_update.pulse(10 * ns)

    @kernel
    def get_mu(self) -> TTuple([TInt64, TInt32]):
        """Get the frequency tuning word and phase offset word.

        .. seealso:: :meth:`get`

        :return: A tuple ``(ftw, pow)``.
        """

        # Read data
        high = self.read(AD9912_POW1, 4)
        self.core.break_realtime()  # Regain slack to perform second read
        low = self.read(AD9912_FTW3, 4)
        # Extract and return fields
        ftw = (int64(high & 0xffff) << 32) | (int64(low) & int64(0xffffffff))
        pow_ = (high >> 16) & 0x3fff
        return ftw, pow_

    @portable(flags={"fast-math"})
    def frequency_to_ftw(self, frequency: TFloat) -> TInt64:
        """Returns the 48-bit frequency tuning word corresponding to the given
        frequency.
        """
        return int64(round(self.ftw_per_hz * frequency)) & (
                (int64(1) << 48) - 1)

    @portable(flags={"fast-math"})
    def ftw_to_frequency(self, ftw: TInt64) -> TFloat:
        """Returns the frequency corresponding to the given
        frequency tuning word.
        """
        return ftw / self.ftw_per_hz

    @portable(flags={"fast-math"})
    def turns_to_pow(self, phase: TFloat) -> TInt32:
        """Returns the 16-bit phase offset word corresponding to the given
        phase.
        """
        return int32(round((1 << 14) * phase)) & 0xffff

    @portable(flags={"fast-math"})
    def pow_to_turns(self, pow_: TInt32) -> TFloat:
        """Return the phase in turns corresponding to a given phase offset
        word.

        :param pow_: Phase offset word.
        :return: Phase in turns.
        """
        return pow_ / (1 << 14)

    @kernel
    def set(self, frequency: TFloat, phase: TFloat = 0.0):
        """Set profile 0 data in SI units.

        .. seealso:: :meth:`set_mu`

        :param frequency: Frequency in Hz
        :param phase: Phase tuning word in turns
        """
        self.set_mu(self.frequency_to_ftw(frequency),
                    self.turns_to_pow(phase))

    @kernel
    def get(self) -> TTuple([TFloat, TFloat]):
        """Get the frequency and phase.

        .. seealso:: :meth:`get_mu`

        :return: A tuple ``(frequency, phase)``.
        """

        # Get values
        ftw, pow_ = self.get_mu()
        # Convert and return
        return self.ftw_to_frequency(ftw), self.pow_to_turns(pow_)

    @kernel
    def cfg_sw(self, state: TBool):
        """Set CPLD CFG RF switch state. The RF switch is controlled by the
        logical or of the CPLD configuration shift register
        RF switch bit and the SW TTL line (if used).

        :param state: CPLD CFG RF switch bit
        """
        self.cpld.cfg_sw(self.chip_select - 4, state)
