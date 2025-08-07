from numpy import int32, int64

from artiq.language.core import *
from artiq.language.units import ms, us, ns
from artiq.coredevice.ad9912_reg import *

from artiq.coredevice.core import Core
from artiq.coredevice.spi2 import *
from artiq.coredevice.urukul import *
from artiq.coredevice.ttl import TTLOut


@compile
class AD9912:
    """
    AD9912 DDS channel on Urukul.

    This class supports a single DDS channel and exposes the DDS,
    the digital step attenuator, and the RF switch.

    :param chip_select: Chip select configuration. On Urukul this is an
        encoded chip select and not "one-hot".
    :param cpld_device: Name of the Urukul CPLD this device is on.
    :param sw_device: Name of the RF switch device. The RF switch is a
        TTLOut channel available as the :attr:`sw` attribute of this instance.
    :param pll_n: DDS PLL multiplier. The DDS sample clock is
        ``f_ref / clk_div * pll_n`` where ``f_ref`` is the reference frequency and 
        ``clk_div`` is the reference clock divider (both set in the parent 
        Urukul CPLD instance).
    :param pll_en: PLL enable bit, set to False to bypass PLL (default: True).
        Note that when bypassing the PLL the red front panel LED may remain on.
    """

    core: KernelInvariant[Core]
    cpld: KernelInvariant[CPLD]
    bus: KernelInvariant[SPIMaster]
    chip_select: KernelInvariant[int32]
    pll_n: KernelInvariant[int32]
    pll_en: KernelInvariant[bool]
    ftw_per_hz: KernelInvariant[float]
    sw: KernelInvariant[Option[TTLOut]]
    io_update: KernelInvariant[TTLOut]

    def __init__(self, dmgr, chip_select, cpld_device, sw_device=None,
                 pll_n=10, pll_en=True):
        self.cpld = dmgr.get(cpld_device)
        self.core = self.cpld.core
        self.bus = self.cpld.bus
        assert 4 <= chip_select <= 7
        self.chip_select = chip_select
        if sw_device:
            self.sw = Some(dmgr.get(sw_device))
        else:
            self.sw = none
        self.pll_en = pll_en
        self.pll_n = pll_n
        if pll_en:
            refclk = self.cpld.refclk
            if refclk < 11e6:
                # use SYSCLK PLL Doubler
                refclk = refclk * 2
            sysclk = refclk / [1, 1, 2, 4][self.cpld.clk_div] * pll_n
        else:
            sysclk = self.cpld.refclk
        assert sysclk <= 1e9
        self.ftw_per_hz = 1 / sysclk * (1 << 48)

        if not self.cpld.io_update:
            self.io_update = urukul.RegIOUpdate(self.cpld, self.chip_select)
        else:
            self.io_update = self.cpld.io_update

    @kernel
    def write(self, addr: int32, data: int32, length: int32):
        """Variable length write to a register.
        Up to 4 bytes.

        :param addr: Register address
        :param data: Data to be written: int32
        :param length: Length in bytes (1-4)
        """
        assert length > 0
        assert length <= 4
        self.bus.set_config_mu(SPI_CONFIG, 16,
                               SPIT_DDS_WR, self.chip_select)
        self.bus.write((addr | ((length - 1) << 13)) << 16)
        self.bus.set_config_mu(SPI_CONFIG | SPI_END, length * 8,
                               SPIT_DDS_WR, self.chip_select)
        self.bus.write(data << (32 - length * 8))

    @kernel
    def read(self, addr: int32, length: int32) -> int32:
        """Variable length read from a register.
        Up to 4 bytes.

        :param addr: Register address
        :param length: Length in bytes (1-4)
        :return: Data read
        """
        assert length > 0
        assert length <= 4
        self.bus.set_config_mu(SPI_CONFIG, 16,
                               SPIT_DDS_WR, self.chip_select)
        self.bus.write((addr | ((length - 1) << 13) | 0x8000) << 16)
        self.bus.set_config_mu(SPI_CONFIG | SPI_END
                               | SPI_INPUT, length * 8,
                               SPIT_DDS_RD, self.chip_select)
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
        ``IO_UPDATE`` signal multiple times.
        """
        # SPI mode
        self.write(AD9912_SER_CONF, 0x99, 1)
        self.io_update.pulse(2. * us)
        # Verify chip ID and presence
        prodid = self.read(AD9912_PRODIDH, 2)
        if (prodid != 0x1982) and (prodid != 0x1902):
            raise ValueError("Urukul AD9912 product id mismatch")
        self.core.delay(50. * us)
        # HSTL power down, CMOS power down
        pwrcntrl1 = 0x80 | (int32(not self.pll_en) << 4)
        self.write(AD9912_PWRCNTRL1, pwrcntrl1, 1)
        self.io_update.pulse(2. * us)
        if self.pll_en:
            self.write(AD9912_N_DIV, self.pll_n // 2 - 2, 1)
            self.io_update.pulse(2. * us)
            # I_cp = 375 µA, VCO high range
            if self.cpld.refclk < 11e6:
                # enable SYSCLK PLL Doubler
                self.write(AD9912_PLLCFG, 0b00001101, 1)
            else:
                self.write(AD9912_PLLCFG, 0b00000101, 1)
            self.io_update.pulse(2. * us)
        self.core.delay(1. * ms)

    @kernel
    def set_att_mu(self, att: int32):
        """Set digital step attenuator in machine units.

        This method will write the attenuator settings of all four channels.

        See also :meth:`~artiq.coredevice.urukul.CPLD.set_att_mu`.

        :param att: Attenuation setting, 8-bit digital.
        """
        self.cpld.set_att_mu(self.chip_select - 4, att)

    @kernel
    def set_att(self, att: float):
        """Set digital step attenuator in SI units.

        This method will write the attenuator settings of all four channels.

        See also :meth:`~artiq.coredevice.urukul.CPLD.set_att`.

        :param att: Attenuation in dB. Higher values mean more attenuation.
        """
        self.cpld.set_att(self.chip_select - 4, att)

    @kernel
    def get_att_mu(self) -> int32:
        """Get digital step attenuator value in machine units.

        See also :meth:`~artiq.coredevice.urukul.CPLD.get_channel_att_mu`.

        :return: Attenuation setting, 8-bit digital.
        """
        return self.cpld.get_channel_att_mu(self.chip_select - 4)

    @kernel
    def get_att(self) -> float:
        """Get digital step attenuator value in SI units.

        See also :meth:`~artiq.coredevice.urukul.CPLD.get_channel_att`.

        :return: Attenuation in dB.
        """
        return self.cpld.get_channel_att(self.chip_select - 4)

    @kernel
    def set_mu(self, ftw: int64, pow_: int32 = 0):
        """Set profile 0 data in machine units.

        After the SPI transfer, the shared IO update pin is pulsed to
        activate the data.

        :param ftw: Frequency tuning word: 48-bit unsigned.
        :param pow_: Phase tuning word: 16-bit unsigned.
        """
        # streaming transfer of FTW and POW
        self.bus.set_config_mu(SPI_CONFIG, 16,
                               SPIT_DDS_WR, self.chip_select)
        self.bus.write((AD9912_POW1 << 16) | (3 << 29))
        self.bus.set_config_mu(SPI_CONFIG, 32,
                               SPIT_DDS_WR, self.chip_select)
        self.bus.write((pow_ << 16) | (int32(ftw >> 32) & 0xffff))
        self.bus.set_config_mu(SPI_CONFIG | SPI_END, 32,
                               SPIT_DDS_WR, self.chip_select)
        self.bus.write(int32(ftw))
        self.io_update.pulse(10. * ns)

    @kernel
    def get_mu(self) -> tuple[int64, int32]:
        """Get the frequency tuning word and phase offset word.

        See also :meth:`AD9912.get`.

        :return: A tuple (FTW, POW).
        """

        # Read data
        high = self.read(AD9912_POW1, 4)
        self.core.break_realtime()  # Regain slack to perform second read
        low = self.read(AD9912_FTW3, 4)
        # Extract and return fields
        ftw = (int64(high & 0xffff) << 32) | (int64(low) & int64(0xffffffff))
        pow_ = (high >> 16) & 0x3fff
        return ftw, pow_

    @portable
    def frequency_to_ftw(self, frequency: float) -> int64:
        """Returns the 48-bit frequency tuning word corresponding to the given
        frequency.
        """
        return round64(self.ftw_per_hz * frequency) & (
                (int64(1) << 48) - int64(1))

    @portable
    def ftw_to_frequency(self, ftw: int64) -> float:
        """Returns the frequency corresponding to the given
        frequency tuning word.
        """
        return float(ftw) / self.ftw_per_hz

    @portable
    def turns_to_pow(self, phase: float) -> int32:
        """Returns the 16-bit phase offset word corresponding to the given
        phase.
        """
        return int32(round(float(1 << 14) * phase)) & 0xffff

    @portable
    def pow_to_turns(self, pow_: int32) -> float:
        """Return the phase in turns corresponding to a given phase offset
        word.

        :param pow_: Phase offset word.
        :return: Phase in turns.
        """
        return pow_ / (1 << 14)

    @kernel
    def set(self, frequency: float, phase: float = 0.0):
        """Set profile 0 data in SI units.

        See also :meth:`AD9912.set_mu`.

        :param frequency: Frequency in Hz
        :param phase: Phase tuning word in turns
        """
        self.set_mu(self.frequency_to_ftw(frequency),
                    self.turns_to_pow(phase))

    @kernel
    def get(self) -> tuple[float, float]:
        """Get the frequency and phase.

        See also :meth:`AD9912.get_mu`.

        :return: A tuple (frequency, phase).
        """

        # Get values
        ftw, pow_ = self.get_mu()
        # Convert and return
        return self.ftw_to_frequency(ftw), self.pow_to_turns(pow_)

    @kernel
    def cfg_sw(self, state: bool):
        """Set CPLD CFG RF switch state. The RF switch is controlled by the
        logical or of the CPLD configuration shift register
        RF switch bit and the SW TTL line (if used).

        :param state: CPLD CFG RF switch bit
        """
        self.cpld.cfg_sw(self.chip_select - 4, state)

    @kernel
    def cfg_mask_nu(self, state: bool):
        """Set CPLD CFG MASK_NU state.

        :param state: CPLD CFG MASK_NU bit
        """
        self.cpld.cfg_mask_nu(self.chip_select - 4, state)

    @kernel
    def cfg_att_en(self, state: bool):
        """Set CPLD CFG ATT_EN state.

        :param state: CPLD CFG ATT_EN bit
        """
        self.cpld.cfg_att_en(self.chip_select - 4, state)
