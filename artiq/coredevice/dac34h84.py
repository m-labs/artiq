from numpy import int32, int64

from artiq.coredevice import spi2 as spi
from artiq.coredevice.dac34h84_reg import DAC34H84 as DAC34H84Reg
from artiq.language.core import *
from artiq.language.types import *
from artiq.language.units import us, GHz


DAC_SPI_DIV = 20  # min 100 ns - SLAS751D Section 6.8
DAC_SPI_DIV_TEMP = (
    200  # min 1 us when reading DAC temperature register - SLAS751D Section 6.8
)
DAC_SPI_CONFIG = (
    0 * spi.SPI_OFFLINE
    | 1 * spi.SPI_END
    | 0 * spi.SPI_INPUT
    | 0 * spi.SPI_CS_POLARITY
    | 0 * spi.SPI_CLK_POLARITY
    | 0 * spi.SPI_CLK_PHASE
    | 0 * spi.SPI_LSB_FIRST
    | 0 * spi.SPI_HALF_DUPLEX
)


class DAC34H84:
    """DAC DAC34H84 driver

    :param spi_device: SPI bus device name.
    :param input_sample_rate: DAC input sample rate
    :param core_device: Core device name (default: "core").
    """

    kernel_invariants = {"core", "bus", "f_dac", "input_sample_rate", "init_mmap"}

    def __init__(
        self,
        dmgr,
        spi_device,
        input_sample_rate,
        core_device="core",
    ):
        self.core = dmgr.get(core_device)
        self.bus = dmgr.get(spi_device)

        self.f_dac = 1.0 * GHz
        self.input_sample_rate = input_sample_rate
        settings = {
            # Target 1 GSPS for all channels, set VCO = 4 GHz and per-scaler = 4
            "pll_p": 0b100,
            "pll_vco": 0x3F,
        }
        # f_ostr must be f_daclk/(k*8*interpolation) where k is integer - SLAS751D Section 6.8
        # f_pdf = f_ostr when PLL is enable - SLAA584 Figure 28
        if input_sample_rate == 500e6:
            # f_data = 500 MSPS (non-interleaved), 2x to reach 1 GSPS
            settings["interpolation"] = 1

            # f_ostr = f_pdf = 62.5 MHz when n divider is 2
            settings["pll_n"] = 0b0001
            # VCO @ 4 GHz when m divider is 16 and no need for m doubling
            settings["pll_m"] = 16
            settings["pll_m2"] = 0

        elif input_sample_rate == 250e6:
            # f_data = 250 MSPS (non-interleaved), 4x to reach 1 GSPS
            settings["interpolation"] = 2

            # f_ostr = f_pdf = 31.25 MHz when n divider is 4
            settings["pll_n"] = 0b0011
            # VCO @ 4 GHz when m divider is 32 and no need for m doubling
            settings["pll_m"] = 32
            settings["pll_m2"] = 0
        else:
            raise ValueError("Invalid DAC sample rate")

        self.init_mmap = DAC34H84Reg(settings).get_mmap()

    @kernel
    def init(self):
        """Initialize the DAC.

        Sets up SPI mode, confirms chip presence, configures the PLL, and sets up FIFO offset.
        """
        # set sif4_enable to enter 4-wire SPI mode
        self.write(0x02, 0x0080)
        if self.read(0x7F) != 0x5409:
            raise ValueError("DAC34H84 version mismatch")
        delay(40.0 * us)
        if self.read(0x00) != 0x049C:
            raise ValueError("DAC34H84 reset fail")
        delay(40.0 * us)

        for data in self.init_mmap:
            self.write(data >> 16, data & 0xFFFF)

        reg_0x18 = self.read(0x18)
        delay(40.0 * us)
        # Use PLL loop filter voltage to check lock status - Table 10, Step 34 SLAS751D section 7.5.2.4
        if not (0x2 <= reg_0x18 & 0b111 <= 0x5):
            raise ValueError("DAC34H84 PLL fail to lock")

        # Disable PLL N-dividers sync - Table 10, Step 41 SLAS751D section 7.5.2.4
        self.write(0x18, reg_0x18 & ~0x0800)

        self.tune_fifo_offset()

    @kernel
    def read(self, addr, div=DAC_SPI_DIV) -> TInt32:
        self.bus.set_config_mu(
            DAC_SPI_CONFIG | spi.SPI_INPUT,
            24,
            div,
            1,
        )
        self.bus.write((addr | 0x80) << 24)
        return self.bus.read()

    @kernel
    def write(self, addr, value, div=DAC_SPI_DIV):
        self.bus.set_config_mu(
            DAC_SPI_CONFIG,
            24,
            div,
            1,
        )
        self.bus.write(addr << 24 | value << 8)

    @kernel
    def read_temperature(self) -> TInt32:
        """Return the current DAC temperature in Celsius.

        This method consumes all slack.
        """
        return self.read(0x06, DAC_SPI_DIV_TEMP) >> 8

    @kernel
    def tune_fifo_offset(self):
        """Find and set an optimal FIFO offset with maximum safety margin."""
        reg_0x09 = self.read(0x09)
        delay(40.0 * us)

        DAC_FIFO_DEPTH = 8
        good = 0
        for offset in range(DAC_FIFO_DEPTH):
            self.write(0x09, (reg_0x09 & 0x1FFF) | ((offset & 0b111) << 13))

            # clear alarm and let it run for a while
            self.write(0x05, 0x0000)
            delay(100.0 * us)

            # check FIFO pointer collision alarm
            if (self.read(0x05) >> 11) & 0b111 == 0:
                good |= 1 << offset
            delay(40.0 * us)

        # If good offset is at both ends, shift the samples for easy mean calculation
        if good & 0x81 == 0x81:
            good_2x = good << DAC_FIFO_DEPTH | good
            good = (good_2x >> (DAC_FIFO_DEPTH // 2)) & ((1 << DAC_FIFO_DEPTH) - 1)
            shift = 4
        else:
            shift = 0
        # calculate mean
        sum = 0
        count = 0
        for offset in range(DAC_FIFO_DEPTH):
            if good & (1 << offset):
                sum += offset
                count += 1
        if count == 0:
            raise ValueError("no good FIFO offset")
        best = ((sum // count) + shift) % 8
        self.write(0x09, (reg_0x09 & 0x1FFF) | ((best & 0b111) << 13))
        # clear alarm in case the last offset tested caused pointer collision
        self.write(0x05, 0x0000)

    @kernel
    def enable_mixer(self, enable):
        """Enable DAC internal mixer block and NCO mixer.

        :param enable: Enable internal mixer block and NCO mixer when set to True
        """
        reg = self.read(0x02)
        delay(40.0 * us)
        if en:
            self.write(0x02, reg | 1 << 6 | 1 << 4)
        else:
            self.write(0x02, reg & ~(1 << 4) & ~(1 << 6))

    @kernel
    def sync(self):
        """Trigger DAC synchronisation for both output channels.

        The DAC ``sif_sync`` is de-asserted, then asserted. The synchronisation is
        triggered on assertion.

        By default, the fine-mixer (NCO) and QMC are synchronised. This
        includes applying the latest register settings.

        .. note:: Synchronising the NCO clears the phase-accumulator.
        """
        reg = self.read(0x1F)
        delay(40.0 * us)
        self.write(0x1F, reg & ~0x2)
        self.write(0x1F, reg | 0x2)

    @kernel
    def stage_nco_mixer_frequency_mu(self, channel, ftw):
        """Stage the DAC NCO mixer frequency in machine units.

        Before using NCO mixer, the mixer must be enabled via :meth:`enable_mixer`.
        The settings is only applied after triggering DAC synchronisation via :meth:`sync`.

        .. warning:: A new NCO settings without synchronisation will result in a malformed channel output.

        :param channel: NCO channel number (0 or 1)
        :param ftw: 32-bit NCO frequency tuning word
        """
        if channel == 0:
            self.write(0x14, ftw & 0xFFFF)
            self.write(0x15, (ftw >> 16) & 0xFFFF)
        elif channel == 1:
            self.write(0x16, ftw & 0xFFFF)
            self.write(0x17, (ftw >> 16) & 0xFFFF)
        else:
            raise ValueError("Invalid channel number")

    @kernel
    def stage_nco_mixer_phase_offset_mu(self, channel, pow):
        """Stage the DAC NCO mixer phase offset in machine units.

        Before using NCO mixer, the mixer must be enabled via :meth:`enable_mixer`.
        The settings is only applied after triggering DAC synchronisation via :meth:`sync`.

        .. warning:: A new NCO settings without synchronisation will result in a malformed channel output.

        :param channel: NCO channel number (0 or 1)
        :param ftw: 16-bit NCO phase offset word
        """
        if channel == 0:
            self.write(0x12, pow)
        elif channel == 1:
            self.write(0x13, pow)
        else:
            raise ValueError("Invalid channel number")

    @portable(flags={"fast-math"})
    def frequency_to_ftw(self, frequency) -> TInt32:
        """Return the 32-bit frequency tuning word corresponding to the given frequency in Hz.

        :param frequency: Frequency in Hz
        """
        return int32(round((int64(1) << 32) * (frequency / (self.f_dac))))

    @portable(flags={"fast-math"})
    def turns_to_pow(self, turns) -> TInt32:
        """Return the 16-bit phase offset word corresponding to the given phase in turns.

        :param turns: Phase offset in turns (0.0 to 1.0)
        """
        return int32(round(turns * (1 << 16)))

    @kernel
    def stage_nco_mixer_frequency(self, channel, frequency):
        """Stage the DAC NCO mixer frequency in SI units.

        Before using NCO mixer, the mixer must be enabled via :meth:`enable_mixer`.
        The settings is only applied after triggering DAC synchronisation via :meth:`sync`.

        .. warning:: A new NCO settings without synchronisation will in a malformed channel output.

        :param channel: NCO channel number (0 or 1)
        :param frequency: NCO frequency in Hz (-500 MHz to +500 MHz)
        """
        self.stage_nco_mixer_frequency_mu(channel, self.frequency_to_ftw(frequency))

    @kernel
    def stage_nco_mixer_phase_offset(self, channel, phase):
        """Stage the DAC NCO mixer phase offset in SI units.

        Before using NCO mixer, the mixer must be enabled via :meth:`enable_mixer`.
        The settings is only applied after triggering DAC synchronisation via :meth:`sync`.

        .. warning:: A new NCO settings without synchronisation will in a malformed channel output.

        :param channel: NCO channel number (0 or 1)
        :param phase: NCO phase offset in turns (0.0 to 1.0)
        """
        self.stage_nco_mixer_phase_offset_mu(channel, self.turns_to_pow(phase))
