"""
RTIO Driver for the Analog Devices AD9834 DDS via 3-wire SPI interface.
"""

# https://www.analog.com/media/en/technical-documentation/data-sheets/AD9834.pdf
# https://www.analog.com/media/en/technical-documentation/app-notes/an-1070.pdf

from numpy import int32

from artiq.coredevice import spi2 as spi
from artiq.experiment import *
from artiq.language.core import *
from artiq.language.types import *
from artiq.language.units import *

AD9834_B28 = 1 << 13
AD9834_HLB = 1 << 12
AD9834_FSEL = 1 << 11
AD9834_PSEL = 1 << 10
AD9834_PIN_SW = 1 << 9
AD9834_RESET = 1 << 8
AD9834_SLEEP1 = 1 << 7
AD9834_SLEEP12 = 1 << 6
AD9834_OPBITEN = 1 << 5
AD9834_SIGN_PIB = 1 << 4
AD9834_DIV2 = 1 << 3
AD9834_MODE = 1 << 1

AD9834_FREQ_REG_0 = 0b01 << 14
AD9834_FREQ_REG_1 = 0b10 << 14
FREQ_REGS = [AD9834_FREQ_REG_0, AD9834_FREQ_REG_1]

AD9834_PHASE_REG = 0b11 << 14
AD9834_PHASE_REG_0 = AD9834_PHASE_REG | (0 << 13)
AD9834_PHASE_REG_1 = AD9834_PHASE_REG | (1 << 13)
PHASE_REGS = [AD9834_PHASE_REG_0, AD9834_PHASE_REG_1]


class AD9834:
    """
    AD9834 DDS driver.

    This class provides control for the DDS AD9834.

    The driver utilizes bit-controlled :const:`AD9834_FSEL`, :const:`AD9834_PSEL`, and
    :const:`AD9834_RESET`. To pin control ``FSELECT``, ``PSELECT``, and ``RESET`` set
    :const:`AD9834_PIN_SW`. The ``ctrl_reg`` attribute is used to maintain the state of
    the control register, enabling persistent management of various configurations.

    :param spi_device: SPI bus device name.
    :param spi_freq: SPI bus clock frequency (default: 10 MHz, max: 40 MHz).
    :param clk_freq: DDS clock frequency (default: 75 MHz).
    :param core_device: Core device name (default: "core").
    """

    kernel_invariants = {"core", "bus", "spi_freq", "clk_freq"}

    def __init__(
        self, dmgr, spi_device, spi_freq=10 * MHz, clk_freq=75 * MHz, core_device="core"
    ):
        self.core = dmgr.get(core_device)
        self.bus = dmgr.get(spi_device)
        assert spi_freq <= 40 * MHz, "SPI frequency exceeds maximum value of 40 MHz"
        self.spi_freq = spi_freq
        self.clk_freq = clk_freq
        self.ctrl_reg = 0x0000  # Reset control register

    @kernel
    def write(self, data: TInt32):
        """
        Write a 16-bit word to the AD9834.

        This method sends a 16-bit data word to the AD9834 via the SPI bus. The input
        data is left-shifted by 16 bits to ensure proper alignment for the SPI controller,
        allowing for accurate processing of the command by the AD9834.

        This method is used internally by other methods to update the control registers
        and frequency settings of the AD9834. It should not be called directly unless
        low-level register manipulation is required.

        :param data: The 16-bit word to be sent to the AD9834.
        """
        self.bus.write(data << 16)

    @kernel
    def enable_reset(self):
        """
        Enable the DDS reset.

        This method sets :const:`AD9834_RESET`, putting the AD9834 into a reset state.
        While in this state, the digital-to-analog converter (DAC) is not operational.

        This method should be called during initialization or when a reset is required
        to reinitialize the device and ensure proper operation.
        """
        self.ctrl_reg |= AD9834_RESET
        self.write(self.ctrl_reg)

    @kernel
    def output_enable(self):
        """
        Disable the DDS reset and start signal generation.

        This method clears :const:`AD9834_RESET`, allowing the AD9834 to begin generating
        signals. Once this method is called, the device will resume normal operation and
        output the generated waveform.

        This method should be called after configuration of the frequency and phase
        settings to activate the output.
        """
        self.ctrl_reg &= ~AD9834_RESET
        self.write(self.ctrl_reg)

    @kernel
    def init(self):
        """
        Initialize the AD9834: configure the SPI bus and reset the DDS.

        This method performs the necessary setup for the AD9834 device, including:
        - Configuring the SPI bus parameters (clock polarity, data width, and frequency).
        - Putting the AD9834 into a reset state to ensure proper initialization.

        The SPI bus is configured to use 16 bits of data width with the clock frequency
        provided as a parameter when creating the AD9834 instance. After configuring
        the SPI bus, the method invokes :meth:`enable_reset()` to reset the AD9834.
        This is an essential step to prepare the device for subsequent configuration
        of frequency and phase.

        This method should be called before any other operations are performed
        on the AD9834 to ensure that the device is in a known state.
        """
        self.bus.set_config(spi.SPI_CLK_POLARITY | spi.SPI_END, 16, self.spi_freq, 1)
        self.enable_reset()

    @kernel
    def set_frequency_reg_msb(self, freq_reg: TInt32, word: TInt32):
        """
        Set the fourteen most significant bits MSBs of the specified frequency register.

        This method updates the specified frequency register with the provided MSB value.
        It configures the control register to indicate that the MSB is being set.

        :param freq_reg: The frequency register to write to (0-1).
        :param word: The value to be written to the fourteen MSBs of the frequency register.

        The method first clears the appropriate control bits, sets :const:`AD9834_HLB` to
        indicate that the MSB is being sent, and then writes the updated control register
        followed by the MSB value to the specified frequency register.
        """
        assert 0 <= freq_reg <= 1, "Invalid frequency register index"
        self.ctrl_reg &= ~AD9834_B28
        self.ctrl_reg |= AD9834_HLB
        self.write(self.ctrl_reg)
        self.write(FREQ_REGS[freq_reg] | (word & 0x3FFF))

    @kernel
    def set_frequency_reg_lsb(self, freq_reg: TInt32, word: TInt32):
        """
        Set the fourteen least significant bits LSBs of the specified frequency register.

        This method updates the specified frequency register with the provided LSB value.
        It configures the control register to indicate that the LSB is being set.

        :param freq_reg: The frequency register to write to (0-1).
        :param word: The value to be written to the fourteen LSBs of the frequency register.

        The method first clears the appropriate control bits and writes the updated control
        register followed by the LSB value to the specified frequency register.
        """
        assert 0 <= freq_reg <= 1, "Invalid frequency register index"
        self.ctrl_reg &= ~AD9834_B28
        self.ctrl_reg &= ~AD9834_HLB
        self.write(self.ctrl_reg)
        self.write(FREQ_REGS[freq_reg] | (word & 0x3FFF))

    @kernel
    def set_frequency_reg(self, freq_reg: TInt32, freq_word: TInt32):
        """
        Set the frequency for the specified frequency register using a precomputed frequency word.

        This writes to the 28-bit frequency register in one transfer.

        :param freq_reg: The frequency register to write to (0-1).
        :param freq_word: The precomputed frequency word.
        """
        assert 0 <= freq_reg <= 1, "Invalid frequency register index"
        self.ctrl_reg |= AD9834_B28
        self.write(self.ctrl_reg)
        lsb = freq_word & 0x3FFF
        msb = (freq_word >> 14) & 0x3FFF
        self.write(FREQ_REGS[freq_reg] | lsb)
        self.write(FREQ_REGS[freq_reg] | msb)

    @portable(flags={"fast-math"})
    def frequency_to_ftw(self, frequency: TFloat) -> TInt32:
        """Return the 28-bit frequency tuning word corresponding to the given
        frequency.
        """
        assert frequency <= 37.5 * MHz, "Frequency exceeds maximum value of 37.5 MHz"
        return int((frequency * (1 << 28)) / self.clk_freq) & 0x0FFFFFFF

    @portable(flags={"fast-math"})
    def turns_to_pow(self, turns: TFloat) -> TInt32:
        """Return the 12-bit phase offset word corresponding to the given phase
        in turns."""
        assert 0.0 <= turns <= 1.0, "Turns exceeds range 0.0 - 1.0"
        return int32(round(turns * 0x1000)) & int32(0x0FFF)

    @kernel
    def select_frequency_reg(self, freq_reg: TInt32):
        """
        Select the active frequency register for the phase accumulator.

        This method chooses between the two available frequency registers in the AD9834 to
        control the frequency of the output waveform. The control register is updated
        to reflect the selected frequency register.

        :param freq_reg: The frequency register to write to (0-1).
        """
        assert 0 <= freq_reg <= 1, "Invalid frequency register index"
        if freq_reg:
            self.ctrl_reg |= AD9834_FSEL
        else:
            self.ctrl_reg &= ~AD9834_FSEL

        self.ctrl_reg &= ~AD9834_PIN_SW
        self.write(self.ctrl_reg)

    @kernel
    def set_phase_reg(self, phase_reg: TInt32, phase: TInt32):
        """
        Set the phase for the specified phase register.

        This method updates the specified phase register with the provided phase value.

        :param phase_reg: The phase register to write to (0-1).
        :param phase: The value to be written to the phase register.

        The method masks the phase value to ensure it fits within the 12-bit limit
        and writes it to the specified phase register.
        """
        assert 0 <= phase_reg <= 1, "Invalid phase register index"
        phase_word = phase & 0x0FFF
        self.write(PHASE_REGS[phase_reg] | phase_word)

    @kernel
    def select_phase_reg(self, phase_reg: TInt32):
        """
        Select the active phase register for the phase accumulator.

        This method chooses between the two available phase registers in the AD9834 to
        control the phase of the output waveform. The control register is updated
        to reflect the selected phase register.

        :param phase_reg: The phase register to write to (0-1).
        """
        assert 0 <= phase_reg <= 1, "Invalid phase register index"
        if phase_reg:
            self.ctrl_reg |= AD9834_PSEL
        else:
            self.ctrl_reg &= ~AD9834_PSEL

        self.ctrl_reg &= ~AD9834_PIN_SW
        self.write(self.ctrl_reg)

    @kernel
    def sleep(self, dac_pd: bool = False, clk_dis: bool = False):
        """
        Put the AD9834 into sleep mode by selectively powering down the DAC and/or disabling
        the internal clock.

        This method controls the sleep mode behavior of the AD9834 by setting or clearing the
        corresponding bits in the control register. Two independent options can be specified:

        :param dac_pd: Set to ``True`` to power down the DAC (:const:`AD9834_SLEEP12` is set).
            ``False`` will leave the DAC active.
        :param clk_dis: Set to ``True`` to disable the internal clock (:const:`AD9834_SLEEP1` is set).
            ``False`` will keep the clock running.

        Both options can be enabled independently, allowing the DAC and/or clock to be powered down as needed.

        The method updates the control register and writes the changes to the AD9834 device.
        """
        if dac_pd:
            self.ctrl_reg |= AD9834_SLEEP12
        else:
            self.ctrl_reg &= ~AD9834_SLEEP12

        if clk_dis:
            self.ctrl_reg |= AD9834_SLEEP1
        else:
            self.ctrl_reg &= ~AD9834_SLEEP1

        self.write(self.ctrl_reg)

    @kernel
    def awake(self):
        """
        Exit sleep mode and restore normal operation.

        This method brings the AD9834 out of sleep mode by clearing any DAC power-down or
        internal clock disable settings. It calls :meth:`sleep()` with no arguments,
        effectively setting both ``dac_powerdown`` and ``internal_clk_disable`` to ``False``.

        The device will resume generating output based on the current frequency and phase
        settings.
        """
        self.sleep()

    @kernel
    def config_sign_bit_out(
        self,
        high_z: bool = False,
        msb_2: bool = False,
        msb: bool = False,
        comp_out: bool = False,
    ):
        """
        Configure the ``SIGN BIT OUT`` pin for various output modes.

        This method sets the output mode for the ``SIGN BIT OUT`` pin of the AD9834 based on the provided flags.
        The user can enable one of several modes, including high impedance, MSB/2 output, MSB output,
        or comparator output. These modes are mutually exclusive, and passing ``True`` to one flag will
        configure the corresponding mode, while other flags should be left as ``False``.

        :param high_z: Set to ``True`` to place the ``SIGN BIT OUT`` pin in high impedance (disabled) mode.
        :param msb_2: Set to ``True`` to output DAC Data MSB divided by 2 on the ``SIGN BIT OUT`` pin.
        :param msb: Set to ``True`` to output DAC Data MSB on the ``SIGN BIT OUT`` pin.
        :param comp_out: Set to ``True`` to output the comparator signal on the ``SIGN BIT OUT`` pin.

        Only one flag should be set to ``True`` at a time. If no valid mode is selected, the ``SIGN BIT OUT``
        pin will default to high impedance mode.

        The method updates the control register with the appropriate configuration and writes it to the AD9834.
        """
        if high_z:
            self.ctrl_reg &= ~AD9834_OPBITEN
        elif msb_2:
            self.ctrl_reg |= AD9834_OPBITEN
            self.ctrl_reg &= ~(AD9834_MODE | AD9834_SIGN_PIB | AD9834_DIV2)
        elif msb:
            self.ctrl_reg |= AD9834_OPBITEN | AD9834_DIV2
            self.ctrl_reg &= ~(AD9834_MODE | AD9834_SIGN_PIB)
        elif comp_out:
            self.ctrl_reg |= AD9834_OPBITEN | AD9834_SIGN_PIB | AD9834_DIV2
            self.ctrl_reg &= ~AD9834_MODE
        else:
            self.ctrl_reg &= ~AD9834_OPBITEN

        self.write(self.ctrl_reg)

    @kernel
    def enable_triangular_waveform(self):
        """
        Enable triangular waveform generation.

        This method configures the AD9834 to output a triangular waveform. It does so
        by clearing :const:`AD9834_OPBITEN` in the control register and setting :const:`AD9834_MODE`.
        Once this method is called, the AD9834 will begin generating a triangular waveform
        at the frequency set for the selected frequency register.

        This method should be called when a triangular waveform is desired for signal
        generation. Ensure that the frequency is set appropriately before invoking this method.
        """
        self.ctrl_reg &= ~AD9834_OPBITEN
        self.ctrl_reg |= AD9834_MODE
        self.write(self.ctrl_reg)

    @kernel
    def disable_triangular_waveform(self):
        """
        Disable triangular waveform generation.

        This method disables the triangular waveform output by clearing :const:`AD9834_MODE`.
        After invoking this method, the AD9834 will cease generating a triangular waveform.
        The device can then be configured to output other waveform types if needed.

        This method should be called when switching to a different waveform type or
        when the triangular waveform is no longer required.
        """
        self.ctrl_reg &= ~AD9834_MODE
        self.write(self.ctrl_reg)

    @kernel
    def set_mu(
        self,
        freq_word: TInt32 = 0,
        phase_word: TInt32 = 0,
        freq_reg: TInt32 = 0,
        phase_reg: TInt32 = 0,
    ):
        """
        Set DDS frequency and phase in machine units.

        This method updates the specified frequency and phase registers with the provided
        machine units, selects the corresponding registers, and enables the output.

        :param freq_word: Frequency tuning word (28-bit).
        :param phase_word: Phase tuning word (12-bit).
        :param freq_reg: Frequency register to write to (0 or 1).
        :param phase_reg: Phase register to write to (0 or 1).
        """
        assert 0 <= freq_reg <= 1, "Invalid frequency register index"
        assert 0 <= phase_reg <= 1, "Invalid phase register index"

        self.set_frequency_reg_lsb(freq_reg, freq_word & 0x3FFF)
        self.set_frequency_reg_msb(freq_reg, (freq_word >> 14) & 0x3FFF)
        self.set_phase_reg(phase_reg, phase_word)
        self.select_frequency_reg(freq_reg)
        self.select_phase_reg(phase_reg)
        self.output_enable()

    @kernel
    def set(
        self,
        frequency: TFloat = 0.0,
        phase: TFloat = 0.0,
        freq_reg: TInt32 = 0,
        phase_reg: TInt32 = 0,
    ):
        """
        Set DDS frequency in Hz and phase using fractional turns.

        This method converts the specified frequency and phase to their corresponding
        machine units, updates the selected registers, and enables the output.

        :param frequency: Frequency in Hz.
        :param phase: Phase in fractional turns (e.g., 0.5 for 180 degrees).
        :param freq_reg: Frequency register to write to (0 or 1).
        :param phase_reg: Phase register to write to (0 or 1).
        """
        assert 0 <= freq_reg <= 1, "Invalid frequency register index"
        assert 0 <= phase_reg <= 1, "Invalid phase register index"

        freq_word = self.frequency_to_ftw(frequency)
        phase_word = self.turns_to_pow(phase)
        self.set_mu(freq_word, phase_word, freq_reg, phase_reg)
