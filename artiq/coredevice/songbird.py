from artiq.coredevice.rtio import rtio_output
from artiq.experiment import *
from artiq.coredevice.spi2 import SPI_END, SPI_INPUT
from artiq.language.core import kernel, delay
from artiq.language.units import us


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


@portable
def volt_to_mu(volt: TFloat, width=16) -> TInt32:
    """Return the equivalent DAC machine unit value.
    Adjust register width accordingly.
    Valid input range is from -1 to 1 - LSB.
    """
    return round((1 << width) * (volt / 2.0)) & ((1 << width) - 1)


class Config:
    """Songbird LTC2000 configuration interface.

    Available as a DC2303A-A FMC connected to the EFC.

    :param spi_device: SPI bus device name.
    :param reset_device: Reset device name.
    :param clear_device: Clear device name.
    """
    kernel_invariants = {"bus", "reset", "clear", "spi_config"}
    
    def __init__(self, dmgr, spi_device, reset_device, clear_device):
        self.bus = dmgr.get(spi_device)
        self.reset = dmgr.get(reset_device)
        self.clear = dmgr.get(clear_device)
        self.spi_config = SPI_END

    @kernel
    def init(self, blind=False):
        self.clear.clear(0b1111)
        # pulse the hardware reset
        self.reset.reset(1)
        delay(1*us)
        self.reset.reset(0)
        delay(1*ms)  # wait for LTC2000 to be ready after reset

        self.software_reset()
        self.configure(blind)

        # de-assert clear to enable DDS outputs
        self.clear.clear(0)

    @kernel
    def software_reset(self):
        self.write_reg(LTC2K_REG_RESET, 0x01)  # Write 1 to the reset bit
        delay(10*ms)  # Wait for reset to complete
        self.write_reg(LTC2K_REG_RESET, 0x00)  # Clear the reset bit
        delay(20*ms)

    @kernel
    def configure(self, blind):
        """Configures the LTC2000 DAC with sensible defaults.

        For more information see the LTC2000 datasheet.
        """
        self.write_reg(LTC2K_REG_RESET, 0x00)  # deassert reset
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

        if not blind:
            # verify the configuration
            if self.read_reg(LTC2K_REG_RESET) != 0x00:
                raise ValueError("LTC2000 reset not deasserted")
            if self.read_reg(LTC2K_REG_CLK) & 0x02 == 0:
                raise ValueError("LTC2000 clock not present")
            if self.read_reg(LTC2K_REG_DCKI) & 0x02 == 0:
                raise ValueError("LTC2000 DCKI not present")

    @kernel
    def write_reg(self, addr, data):
        self.bus.set_config_mu(self.spi_config, 32, 256, 0b0001)
        delay(20*us)
        self.bus.write((addr << 24) | (data << 16))
        delay(2*us)
        self.bus.set_config_mu(self.spi_config, 32, 256, 0b0000)

    @kernel
    def read_reg(self, addr) -> TInt32:
        self.bus.set_config_mu(self.spi_config | SPI_INPUT, 32, 256, 0b0001)
        delay(2*us)
        self.bus.write((1 << 31) | (addr << 24))
        delay(2*us)
        result = self.bus.read()
        delay(2*us)
        self.bus.set_config_mu(self.spi_config, 32, 256, 0b0000)
        value = (result >> 16) & 0xFF
        return value


class DDS:
    """LTC2000 Core DDS spline.

    A LTC2000 channel generates a composite waveform `w(t)` according to:

    ```
    w(t) = b(t) * cos(c(t))
    ```

    and `t` corresponds to time in seconds.
    This class controls the cubic spline `b(t)` and quadratic spline `c(t)`,
    in which

    .. math::
        b(t) &= q_0 + q_1t + \\frac{q_2t^2}{2} + \\frac{q_3t^3}{6}

        c(t) &= r_0 + r_1t + \\frac{r_2t^2}{2}

    `b(t)` is in volts, `c(t)` is in number of turns.

    :param channel: RTIO channel number of this DC-bias spline interface.
    :param core_device: Core device name.
    """
    kernel_invariants = {"core", "b_channel", "c_channel", "dds_freq", "b_target_o", "c_target_o"}

    def __init__(self, dmgr, b_channel, c_channel, core_device="core"):
        self.core = dmgr.get(core_device)
        if self.core.ref_period == 1.25e-9:
            self.dds_freq = 200e6
        elif self.core.ref_period == 1e-9:
            self.dds_freq = 125e6 * 5/3  # 208.33 MHz
        else:
            raise ValueError("Core frequency not supported")
        self.b_channel = b_channel
        self.c_channel = c_channel + 1
        self.b_target_o = self.b_channel << 8
        self.c_target_o = self.c_channel << 8

    @portable
    def frequency_to_mu(self, frequency: TFloat) -> TInt32:
        """Convert frequency in Hz to a 32-bit frequency tuning word (FTW)
        """
        return int32(round(frequency * (1 << 32) / self.dds_freq))

    @kernel
    def set_waveform(self, b0: TInt32, b1: TInt32, b2: TInt64, b3: TInt64,
            c0: TInt32, c1: TInt32, c2: TInt32, shift: TInt32 = 0):
        """Set the DDS spline waveform.

        The shift parameter controls the spline update rate:
        - shift = 0: normal rate (no division)
        - shift = 1: half rate (2x longer duration)
        - shift = 2: quarter rate (4x longer duration)
        - ...
        - shift = 15: 1/32768 rate (32768x longer duration)

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
        - `c0`: initial phase offset, 18-bit word.
        - `c1`: initial frequency, as a 32-bit frequency tuning word (FTW).
          Use :meth:`frequency_to_mu` to convert from Hz.
        - `c2`: frequency chirp rate, as the change in FTW per spline update tick.
          A spline update tick is `(8 ns) * (1 << shift)`.

        :math:`b_0`, :math:`b_1`, :math:`b_2` and :math:`b_3` are 16, 32, 48
        and 48 bits in width respectively. See :meth:`volt_to_mu` for
        machine unit conversion. :math:`c_0`, :math:`c_1` and :math:`c_2` are
        18, 32 and 32 bits in width respectively.

        Note: The waveform is not updated to the LTC2000 Core until
        triggered. See :class:`Trigger` for the update triggering mechanism.

        **Examples:**
        Constant Amplitude Sine Wave: b(t) = 1.0V, c(t) = f₀t

            dds.set_waveform(b0=volt_to_mu(1.0), b1=0, b2=0, b3=0, c0=0,
                             c1=dds.frequency_to_mu(1e6), c2=0, shift=0)

        Linear Frequency Sweep: chirped sine, constant amplitude

            dds.set_waveform(b0=volt_to_mu(0.5), b1=0, b2=0, b3=0,
                             c0=0, c1=dds.frequency_to_mu(10e6), c2=chirp_rate_mu, shift=3)

        Amplitude Modulated Signal: b(t) = A₀ + A₁t (linear amplitude ramp)

            dds.set_waveform(b0=base_amplitude_mu, b1=ramp_rate_mu, b2=0, b3=0,
                             c0=0, c1=carrier_freq_mu, c2=0, shift=1)

        :param b0: The :math:`b_0` coefficient in machine units.
        :param b1: The :math:`b_1` coefficient in machine units.
        :param b2: The :math:`b_2` coefficient in machine units.
        :param b3: The :math:`b_3` coefficient in machine units.
        :param c0: The :math:`c_0` (phase offset) coefficient in machine units.
        :param c1: The :math:`c_1` (frequency) coefficient in machine units.
        :param c2: The :math:`c_2` (chirp) coefficient in machine units.
        :param shift: Clock division factor (0-15). Defaults to 0 (no division).
        """

        self.set_ampl(b0, b1, b2, b3)
        self.set_phase(c0, c1, c2, shift)

    @kernel
    def set_ampl(self, b0: TInt32, b1: TInt32, b2: TInt64, b3: TInt64):
        """Controls only the amplitude part of the waveform.

        As with set_waveform, the changes must be triggered
        before they are applied in the LTC2000 core.
        See :class:`Trigger` for the update triggering mechanism.

        :param b0: The :math:`b_0` coefficient in machine units.
        :param b1: The :math:`b_1` coefficient in machine units.
        :param b2: The :math:`b_2` coefficient in machine units.
        :param b3: The :math:`b_3` coefficient in machine units.
        """

        b_coef_words = [
            b0 & 0xFFFF,                          # Word 0: amplitude offset
            b1 & 0xFFFF,                          # Word 1: damp low
            (b1 >> 16) & 0xFFFF,                  # Word 2: damp high
            b2 & 0xFFFF,                          # Word 3: ddamp low
            (b2 >> 16) & 0xFFFF,                  # Word 4: ddamp mid
            (b2 >> 32) & 0xFFFF,                  # Word 5: ddamp high
            b3 & 0xFFFF,                          # Word 6: dddamp low
            (b3 >> 16) & 0xFFFF,                  # Word 7: dddamp mid
            (b3 >> 32) & 0xFFFF,                  # Word 8: dddamp high
        ]

        for i in range(len(b_coef_words)):
            rtio_output(self.b_target_o | i, b_coef_words[i])
            delay_mu(int64(self.core.ref_multiplier))

    @kernel
    def set_phase(self, c0: TInt32, c1: TInt32, c2: TInt32, shift: TInt32 = 0):
        """Controls the phase, FTW chirp and shift of the waveform. 
            See :meth:`set_waveform` for more details.

        :param c0: The :math:`c_0` (phase offset) coefficient in machine units.
        :param c1: The :math:`c_1` (frequency) coefficient in machine units.
        :param c2: The :math:`c_2` (chirp) coefficient in machine units.
        :param shift: Clock division factor (0-15). Defaults to 0 (no division).
        """        
        if not 0 <= shift <= 15:
            raise ValueError("Shift must be between 0 and 15")

        phase_msb = (c0 >> 2) & 0xFFFF   # Upper 16 bits of 18-bit phase value
        phase_lsb = c0 & 0x3             # Bottom 2 bits of 18-bit phase value
        
        c_coef_words = [
            phase_msb,                            # Word 9: phase offset main (16 bits)
            c1 & 0xFFFF,                          # Word 10: ftw low
            (c1 >> 16) & 0xFFFF,                  # Word 11: ftw high
            c2 & 0xFFFF,                          # Word 12: chirp low
            (c2 >> 16) & 0xFFFF,                  # Word 13: chirp high

            shift | (phase_lsb << 4),             # Word 14: shift[3:0] + phase_lsb[5:4] + reserved[15:6]
        ]

        for i in range(len(c_coef_words)):
            rtio_output(self.c_target_o | i, c_coef_words[i])
            delay_mu(int64(self.core.ref_multiplier))


class Trigger:
    """Shuttler Core spline coefficients update trigger.

    :param b_channel: RTIO channel number of the b coefficients trigger interface.
    :param c_channel: RTIO channel number of the c coefficients trigger interface.
    :param core_device: Core device name.
    """
    kernel_invariants = {"core", "b_channel", "c_channel", "b_target_o", "c_target_o"}

    def __init__(self, dmgr, b_channel, c_channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.b_channel = b_channel
        self.c_channel = c_channel
        self.b_target_o = b_channel << 8
        self.c_target_o = c_channel << 8

    @kernel
    def trigger(self, channels_mask):
        """Triggers coefficient update of LTC2000 Core channel(s).

        The waveform configuration is not applied to the LTC2000 Core until
        explicitly triggered.
        This allows atomic updates across multiple channels.

        This method updates both b and c coefficients. See :meth:`trigger_b`
        and :meth:`trigger_c` for separate updates.

        Each bit corresponds to an LTC2000 waveform generator core. Setting
        bits in `channels_mask` commits the pending coefficient updates to
        the corresponding DDS channels synchronously.

        **Example:**
            # Configure waveforms for dds0
            self.songbird0_dds0.set_waveform(...)

            # Apply the configuration
            self.songbird0_trigger.trigger(1 << 0)  # Trigger amplitude and phase spline for channel 0

        :param channels_mask: Coefficient update trigger bits. The MSB corresponds
            to Channel 15, LSB corresponds to Channel 0.
        """
        with parallel:
            rtio_output(self.b_target_o, channels_mask)
            rtio_output(self.c_target_o, channels_mask)

    @kernel
    def trigger_b(self, channels_mask):
        """Triggers amplitude coefficient update of LTC2000 Core channel(s).

        This method updates only b coefficients. See :meth:`trigger`
        and :meth:`trigger_c` for other update options.

        Each bit corresponds to an LTC2000 waveform generator core. Setting
        bits in `channels_mask` commits the pending coefficient updates to
        the corresponding DDS channels synchronously.

        :param channels_mask: Coefficient update trigger bits. The MSB corresponds
            to Channel 15, LSB corresponds to Channel 0.
        """
        rtio_output(self.b_target_o, channels_mask)

    @kernel
    def trigger_c(self, channels_mask):
        """Triggers amplitude coefficient update of LTC2000 Core channel(s).

        This method updates only c coefficients. See :meth:`trigger`
        and :meth:`trigger_b` for other update options.

        Each bit corresponds to an LTC2000 waveform generator core. Setting
        bits in `channels_mask` commits the pending coefficient updates to
        the corresponding DDS channels synchronously.

        :param channels_mask: Coefficient update trigger bits. The MSB corresponds
            to Channel 15, LSB corresponds to Channel 0.
        """
        rtio_output(self.c_target_o, channels_mask)


class Clear:
    """Shuttler Core clear signal.

    :param channel: RTIO channel number of the clear interface.
    :param core_device: Core device name.
    """
    kernel_invariants = {"core", "channel", "target_o"}

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.target_o = channel << 8

    @kernel
    def clear(self, clear_out):
        """Clears the Shuttler Core channel(s).

        Each bit corresponds to a Shuttler waveform generator core. Setting
        ``clear_out`` bits clears the corresponding channels in the Shuttler Core
        synchronously.

        :param clear_out: Clear signal bits. The MSB corresponds
            to Channel 15, LSB corresponds to Channel 0.
        """
        rtio_output(self.target_o, clear_out)

class Reset:
    """Shuttler Core reset signal.

    :param channel: RTIO channel number of the clear interface.
    :param core_device: Core device name.
    """
    kernel_invariants = {"core", "channel", "target_o"}

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.target_o = channel << 8

    @kernel
    def reset(self, reset):
        """Resets the LTC2000 DAC.

        :param reset: Reset signal.
        """
        rtio_output(self.target_o, reset)