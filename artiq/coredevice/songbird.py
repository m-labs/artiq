from artiq.coredevice.rtio import rtio_output
from artiq.coredevice.spi2 import SPI_END, SPI_INPUT
from artiq.language.core import kernel, delay, delay_mu, portable
from artiq.language.types import TFloat, TInt32, TInt64
from artiq.language.units import ms, us


LTC2K_REG_RESET = 0x01  # Reset, power down controls
LTC2K_REG_CLK   = 0x02  # Clock and DCKO controls
LTC2K_REG_DCKI  = 0x03  # DCKI controls
LTC2K_REG_PORT  = 0x04  # Data input controls
LTC2K_REG_SYNC  = 0x05  # Synchronizer controls
LTC2K_REG_PHASE = 0x06  # Synchronizer phase comparator output
LTC2K_REG_DYN_LIN = 0x07  # Linearization controls
LTC2K_REG_DYN_LIN_V = 0x08  # Linearization voltage controls
LTC2K_REG_GAIN  = 0x09  # DAC gain adjustment controls
LTC2K_REG_TEST  = 0x18  # LVDS test MUX controls  
LTC2K_REG_TEMP  = 0x19  # Temperature measurement controls
LTC2K_REG_PATTERN = 0x1E  # Pattern generator enable
LTC2K_REG_PATTERN_DATA = 0x1F  # Pattern generator data

N_DDS = 4

@portable
def volt_to_mu(volt: TFloat, width=16) -> TInt32:
    """Return the equivalent DAC machine unit value.

    Valid input range is from -1.0 to 1.0.

    :param volt: The voltage to convert.
    :param width: The bit width of the DAC.
    """
    return round((1 << width) * (volt / 2.0)) & ((1 << width) - 1)


class Songbird:
    """Songbird and LTC2000 configuration, trigger and clear interfaces.

    :param spi_device: SPI bus device name.
    :param channel: Base RTIO channel number.
    :param core_device: Core device name (default: "core").
    """
    B_TRIG_OFFSET = 0
    C_TRIG_OFFSET = 1

    kernel_invariants = {"bus", "core", "dds_freq", "spi_config"}
    
    def __init__(self, dmgr, spi_device, channel, core_device="core"):
        self.bus = dmgr.get(spi_device)
        self.core = dmgr.get(core_device)
        if self.core.ref_period == 1.25e-9:
            self.dds_freq = 2.4e9
        elif self.core.ref_period == 1e-9:
            self.dds_freq = 2.5e9
        else:
            raise ValueError("RTIO reference period not supported by Songbird")
        self.target_clear_o = channel << 8
        self.target_reset_o = (channel + 1) << 8
        self.target_trigger_o = (channel + 2) << 8
        self.clear_state = 0
        self.spi_config = SPI_END

    @portable
    def frequency_to_mu(self, frequency: TFloat) -> TInt32:
        """Convert frequency in Hz to a 32-bit frequency tuning word (FTW).

        :param frequency: Frequency in Hz.
        """
        return int32(round(frequency * (2.0**32) / self.dds_freq))

    @kernel
    def init(self):
        """Initializes the LTC2000 DAC.

        Sets up the DAC with sensible defaults.
        For more information, see the LTC2000 datasheet.
        """
        # pulse the hardware reset
        self.reset(True)
        delay(10*us)
        self.reset(False)
        delay(10*ms)  # wait for LTC2000 to be ready after reset

        # configure the LTC2000
        self.write_reg(LTC2K_REG_RESET, 0x01)  # Write 1 to the reset bit
        delay(10*ms)  # Wait for reset to complete
        # reset clears automatically after ~CS is deasserted
        self.write_reg(LTC2K_REG_CLK, 0x00)
        self.write_reg(LTC2K_REG_DCKI, 0x01)  # enable DCKI
        self.write_reg(LTC2K_REG_PORT, 0x03)  # enable Port A and B
        delay(1*ms)  # wait at least 1ms as per startup sequence
        self.write_reg(LTC2K_REG_PORT, 0x0B)  # enable Port A and B + DAC Data Enable
        self.write_reg(LTC2K_REG_SYNC, 0x00)
        self.write_reg(LTC2K_REG_DYN_LIN, 0x00)  # enable linearization with 75%
        self.write_reg(LTC2K_REG_DYN_LIN_V, 0x08)
        self.write_reg(LTC2K_REG_TEST, 0x00)  # no test
        self.write_reg(LTC2K_REG_TEMP, 0x00)  # disable temperature measurement
        self.write_reg(LTC2K_REG_PATTERN, 0x00)  # disable pattern generation
        self.write_reg(LTC2K_REG_PATTERN, 0x00)

        # verify the configuration
        if self.read_reg(LTC2K_REG_RESET) != 0x00:
            raise ValueError("LTC2000 reset not deasserted")
        if self.read_reg(LTC2K_REG_CLK) & 0x02 == 0:
            raise ValueError("LTC2000 clock not present")
        if self.read_reg(LTC2K_REG_DCKI) & 0x02 == 0:
            raise ValueError("LTC2000 DCKI not present")

    @kernel
    def write_reg(self, addr: TInt32, data: TInt32):
        """Write to an LTC2000 register.

        :param addr: Register address.
        :param data: Data to write.
        """
        self.bus.set_config_mu(self.spi_config, 32, 256, 0b0001)
        delay(20*us)
        self.bus.write((addr << 24) | (data << 16))
        delay(2*us)
        self.bus.set_config_mu(self.spi_config, 32, 256, 0b0000)

    @kernel
    def read_reg(self, addr: TInt32) -> TInt32:
        """Read from an LTC2000 register.

        :param addr: Register address.
        :return: The 8-bit value read from the register.
        """
        self.bus.set_config_mu(self.spi_config | SPI_INPUT, 32, 256, 0b0001)
        delay(2*us)
        self.bus.write((1 << 31) | (addr << 24))
        delay(2*us)
        result = self.bus.read()
        delay(2*us)
        self.bus.set_config_mu(self.spi_config, 32, 256, 0b0000)
        value = (result >> 16) & 0xFF
        return value

    @kernel
    def trigger(self, channels_mask: TInt32):
        """Triggers coefficient update of Songbird PHY channel(s).

        The waveform configuration is not applied to the Songbird PHY until
        explicitly triggered.
        This allows atomic updates across multiple channels.

        This method updates both b and c coefficients. See :meth:`trigger_b`
        and :meth:`trigger_c` for separate updates. In the :class:`DDS` class
        you can also find :meth:`trigger` method that will apply to that channel.

        Each bit corresponds to a Songbird waveform generator core. Setting
        bits in ``channels_mask`` commits the pending coefficient updates to
        the corresponding DDS channels synchronously.

        **Examples**

        Example 1::

            # Configure and apply waveforms for dds0
            self.songbird0_dds0.set_waveform(...)
            self.songbird0_dds0.trigger()

        Example 2::

            # Configure and apply waveforms for dds0 and dds1 simultaneously
            self.songbird0_dds0.set_waveform(...)
            self.songbird0_dds1.set_waveform(...)
            self.songbird0_config.trigger(0b11)

        :param channels_mask: Coefficient update trigger bits. The MSB corresponds
            to Channel 3, LSB corresponds to Channel 0.
        """
        rtio_output(self.target_trigger_o | self.B_TRIG_OFFSET, channels_mask)
        delay_mu(int64(self.core.ref_multiplier))
        rtio_output(self.target_trigger_o | self.C_TRIG_OFFSET, channels_mask)

    @kernel
    def trigger_b(self, channels_mask: TInt32):
        """Triggers amplitude coefficient update of Songbird Core channel(s).

        This method updates only b coefficients. See :meth:`trigger`
        and :meth:`trigger_c` for other update options.

        :param channels_mask: Coefficient update trigger bits. The MSB corresponds
            to Channel 3, LSB corresponds to Channel 0.
        """
        rtio_output(self.target_trigger_o | self.B_TRIG_OFFSET, channels_mask)

    @kernel
    def trigger_c(self, channels_mask: TInt32):
        """Triggers phase/frequency coefficient update of Songbird Core channel(s).

        This method updates only c coefficients. See :meth:`trigger`
        and :meth:`trigger_b` for other update options.

        :param channels_mask: Coefficient update trigger bits. The MSB corresponds
            to Channel 3, LSB corresponds to Channel 0.
        """
        rtio_output(self.target_trigger_o | self.C_TRIG_OFFSET, channels_mask)

    @kernel
    def clear(self, clear_out: TInt32):
        """Clears the Songbird Core channel(s). Clearing essentially
        disables the output of the channel.

        Each bit corresponds to a Songbird waveform generator core. Setting
        ``clear_out`` bits disables the output of the corresponding channels 
        in the Songbird Core synchronously. 

        :param clear_out: Clear signal bits. The MSB corresponds
            to Channel 3, LSB corresponds to Channel 0.
        """
        self.clear_state = clear_out
        rtio_output(self.target_clear_o, self.clear_state)

    @kernel
    def clear_channel(self, channel: TInt32, clear: bool):
        """Clear disables the output of a specified Songbird Core channel.
        See also :meth:`clear` for more information.

        :param channel: Channel number.
        :param clear: Disable bit. True disables the output.
        """
        if clear:
            self.clear_state |= 1 << channel
        else:
            self.clear_state &= ~(1 << channel)
        rtio_output(self.target_clear_o, self.clear_state)

    @kernel
    def reset(self, reset: bool):
        """Resets the Songbird DAC.

        :param reset: Reset signal.
        """
        reset_bit = 1 if reset else 0
        rtio_output(self.target_reset_o, reset_bit)


class DDS:
    """Songbird Core DDS spline.

    :param channel: RTIO channel number of this DC-bias spline interface.
    :param config_device: Songbird config device name.
    :param dds_no: DDS channel number.
    :param core_device: Core device name.
    """
    kernel_invariants = {"config", "core", "b_channel", "c_channel", "dds_no", "b_target_o", "c_target_o"}

    def __init__(self, dmgr, channel, config_device, dds_no, core_device="core"):
        self.config = dmgr.get(config_device)
        self.core = dmgr.get(core_device)
        self.dds_no = dds_no
        self.b_channel = channel
        self.c_channel = channel + 1
        self.b_target_o = self.b_channel << 8
        self.c_target_o = self.c_channel << 8

    @kernel
    def trigger(self):
        """Triggers the update of the channel, for both b and c coefficients."""
        self.config.trigger(1 << self.dds_no)

    @kernel
    def trigger_b(self):
        """Triggers the update of the b coefficients of the channel."""
        self.config.trigger_b(1 << self.dds_no)

    @kernel
    def trigger_c(self):
        """Triggers the update of the c coefficients of the channel."""
        self.config.trigger_c(1 << self.dds_no)

    @kernel
    def clear(self, clear=True):
        """Clears the output of the Songbird core channel. That disables the output.

        :param clear: Disable bit.
        """
        self.config.clear_channel(self.dds_no, clear)

    @kernel
    def set_waveform(self, ampl_offset: TInt32, damp: TInt32, ddamp: TInt64, dddamp: TInt64,
            phase_offset: TInt32, ftw: TInt32, chirp: TInt32, shift: TInt32 = 0):
        """Set the DDS spline waveform.

        A Songbird channel generates a composite waveform `w(t)` according to:

        .. math::
            w(t) = b(t) * cos(c(t))

        and where `t` corresponds to time in seconds.
        This class controls the cubic spline `b(t)` and quadratic spline `c(t)`,
        in which

        .. math::
            b(t) &= q_0 + q_1t + \\frac{q_2t^2}{2} + \\frac{q_3t^3}{6}

            c(t) &= r_0 + r_1t + \\frac{r_2t^2}{2}

        `b(t)` is in volts, `c(t)` is in number of turns.

        The shift parameter controls the spline update rate:

        * ``shift = 0``: normal rate (no division)
        * ``shift = 1``: half rate (2x longer duration)
        * ``shift = 2``: quarter rate (4x longer duration)
        * ...
        * ``shift = 15``: 1/32768 rate (32768x longer duration)

        Given `b(t)` and `c(t)` as defined in :class:`DDS`, the coefficients
        should be configured by the following formulae.

        .. math::
            T &= 8*10^{-9}

            b_0 &= q_0

            b_1 &= q_1T + \\frac{q_2T^2}{2} + \\frac{q_3T^3}{6}

            b_2 &= q_2T^2 + q_3T^3

            b_3 &= q_3T^3

            c_0 &= r_0

            c_1 &= r_1T + \\frac{r_2T^2}{2}

            c_2 &= r_2T^2
        
        The coefficients for the amplitude spline `b(t)` are provided in machine
        units. Use :meth:`volt_to_mu` to convert from volts.

        The coefficients for the phase/frequency spline `c(t)` are:

        * ``phase_offset``: initial phase offset, 18-bit word.
        * ``ftw``: initial frequency, as a 32-bit frequency tuning word (FTW).
          Use :meth:`Songbird.frequency_to_mu` to convert from Hz.
        * ``chirp``: frequency chirp rate, as the change in FTW per spline update tick.
          A spline update tick is `(8 ns) * (1 << shift)`.

        :math:`b_0`, :math:`b_1`, :math:`b_2` and :math:`b_3` are 16, 32, 48
        and 48 bits in width respectively. See :meth:`volt_to_mu` for
        machine unit conversion. :math:`c_0`, :math:`c_1` and :math:`c_2` are
        18, 32 and 32 bits in width respectively.

        .. note::
            The waveform is not updated to the Songbird Core until triggered.
            See :meth:`trigger` for the update triggering mechanism.

        **Examples:**
        Constant Amplitude Sine Wave: :math:`b(t) = 1.0V`, :math:`c(t) = f_0t`::

            dds.set_waveform(ampl_offset=volt_to_mu(1.0), damp=0, ddamp=0, dddamp=0,
                phase_offset=0, ftw=songbird.frequency_to_mu(1e6), chirp=0)

        Linear Frequency Sweep: chirped sine, constant amplitude::

            dds.set_waveform(ampl_offset=volt_to_mu(0.5), damp=0, ddamp=0, dddamp=0,
                phase_offset=0, ftw=songbird.frequency_to_mu(10e6), chirp=chirp_rate_mu)

        Amplitude Modulated Signal: :math:`b(t) = A_0 + A_1t` (linear amplitude ramp)::

            dds.set_waveform(ampl_offset=volt_to_mu(0.1), damp=ramp_rate_mu, 
                ddamp=0, dddamp=0, phase_offset=0, ftw=carrier_freq_mu, chirp=0)

        :param ampl_offset: The :math:`b_0` (amplitude offset) coefficient in machine units.
        :param damp: The :math:`b_1` coefficient in machine units.
        :param ddamp: The :math:`b_2` coefficient in machine units.
        :param dddamp: The :math:`b_3` coefficient in machine units.
        :param phase_offset: The :math:`c_0` (phase offset) coefficient in machine units.
        :param ftw: The :math:`c_1` (frequency tuning word) coefficient in machine units.
        :param chirp: The :math:`c_2` (chirp rate) coefficient in machine units.
        :param shift: Clock division factor (0-15). Defaults to 0 (no division).
        """

        self.set_ampl(ampl_offset, damp, ddamp, dddamp)
        self.set_phase(phase_offset, ftw, chirp, shift)

    @kernel
    def set_ampl(self, ampl_offset: TInt32, damp: TInt32, ddamp: TInt64, dddamp: TInt64):
        """Controls only the amplitude part of the waveform.

        As with :meth:`set_waveform`, the changes must be triggered
        before they are applied in the LTC2000 core.
        See :meth:`trigger` for the update triggering mechanism.

        :param ampl_offset: The :math:`b_0` coefficient in machine units.
        :param damp: The :math:`b_1` coefficient in machine units.
        :param ddamp: The :math:`b_2` coefficient in machine units.
        :param dddamp: The :math:`b_3` coefficient in machine units.
        """

        b_coef_words = [
            ampl_offset & 0xFFFF,      # Word 0: amplitude offset
            damp & 0xFFFF,             # Word 1: damp low
            (damp >> 16) & 0xFFFF,     # Word 2: damp high
            ddamp & 0xFFFF,            # Word 3: ddamp low
            (ddamp >> 16) & 0xFFFF,    # Word 4: ddamp mid
            (ddamp >> 32) & 0xFFFF,    # Word 5: ddamp high
            dddamp & 0xFFFF,           # Word 6: dddamp low
            (dddamp >> 16) & 0xFFFF,   # Word 7: dddamp mid
            (dddamp >> 32) & 0xFFFF,   # Word 8: dddamp high
        ]

        for i in range(len(b_coef_words)):
            rtio_output(self.b_target_o | i, b_coef_words[i])
            delay_mu(int64(self.core.ref_multiplier))

    @kernel
    def set_phase(self, phase_offset: TInt32, ftw: TInt32, chirp: TInt32, shift: TInt32 = 0):
        """Controls the phase, FTW, chirp, and shift of the waveform.
        See :meth:`set_waveform` for more details.

        :param phase_offset: The :math:`c_0` coefficient in machine units.
        :param ftw: The :math:`c_1` coefficient in machine units.
        :param chirp: The :math:`c_2` coefficient in machine units.
        :param shift: Clock division factor (0-15). Defaults to 0 (no division).
        """
        if not 0 <= shift <= 15:
            raise ValueError("Shift must be between 0 and 15")

        phase_msb = (phase_offset >> 2) & 0xFFFF  # Upper 16 bits of 18-bit phase value
        phase_lsb = phase_offset & 0x3            # Bottom 2 bits of 18-bit phase value
        
        c_coef_words = [
            phase_msb,                           # Word 9: phase offset main (16 bits)
            ftw & 0xFFFF,                        # Word 10: ftw low
            (ftw >> 16) & 0xFFFF,                # Word 11: ftw high
            chirp & 0xFFFF,                      # Word 12: chirp low
            (chirp >> 16) & 0xFFFF,              # Word 13: chirp high
            shift | (phase_lsb << 4),            # Word 14: shift[3:0] + phase_lsb[5:4] + reserved[15:6]
        ]

        for i in range(len(c_coef_words)):
            rtio_output(self.c_target_o | i, c_coef_words[i])
            delay_mu(int64(self.core.ref_multiplier))
