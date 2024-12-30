from artiq.language.core import *
from artiq.language.types import *
from artiq.coredevice.rtio import rtio_output, rtio_input_data
from artiq.coredevice import spi2 as spi
from artiq.language.units import us


@portable
def shuttler_volt_to_mu(volt):
    """Return the equivalent DAC code. Valid input range is from -10 to
    10 - LSB.
    """
    return round((1 << 16) * (volt / 20.0)) & 0xffff


class Config:
    """Shuttler configuration registers interface.

    The configuration registers control waveform phase auto-clear, pre-DAC
    gain and offset values for calibration with ADC on the Shuttler AFE card.

    To find the calibrated DAC code, the Shuttler Core first multiplies the
    output data with pre-DAC gain, then adds the offset.

    .. note::
        The DAC code is capped at 0x7fff and 0x8000.

    :param channel: RTIO channel number of this interface.
    :param core_device: Core device name.
    """
    kernel_invariants = {
        "core", "channel", "target_base", "target_read",
        "target_gain", "target_offset", "target_clr"
    }

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.target_base   = channel << 8
        self.target_read   = 1 << 6
        self.target_gain   = 0 * (1 << 4)
        self.target_offset = 1 * (1 << 4)
        self.target_clr    = 1 * (1 << 5)

    @kernel
    def set_clr(self, clr):
        """Set/Unset waveform phase clear bits.

        Each bit corresponds to a Shuttler waveform generator core. Setting a
        clear bit forces the Shuttler Core to clear the phase accumulator on
        waveform trigger (See :class:`Trigger` for the trigger method).
        Otherwise, the phase accumulator increments from its original value.

        :param clr: Waveform phase clear bits. The MSB corresponds to Channel
            15, LSB corresponds to Channel 0.
        """
        rtio_output(self.target_base | self.target_clr, clr)
    
    @kernel
    def set_gain(self, channel, gain):
        """Set the 16-bits pre-DAC gain register of a Shuttler Core channel.

        The `gain` parameter represents the decimal portion of the gain
        factor. The MSB represents 0.5 and the sign bit. Hence, the valid
        total gain value (1 +/- 0.gain) ranges from 0.5 to 1.5 - LSB.

        :param channel: Shuttler Core channel to be configured.
        :param gain: Shuttler Core channel gain.
        """
        rtio_output(self.target_base | self.target_gain | channel, gain)
    
    @kernel
    def get_gain(self, channel):
        """Return the pre-DAC gain value of a Shuttler Core channel.

        :param channel: The Shuttler Core channel.
        :return: Pre-DAC gain value. See :meth:`set_gain`.
        """
        rtio_output(self.target_base | self.target_gain |
            self.target_read | channel, 0)
        return rtio_input_data(self.channel)
    
    @kernel
    def set_offset(self, channel, offset):
        """Set the 16-bits pre-DAC offset register of a Shuttler Core channel.

        See also :meth:`shuttler_volt_to_mu`.

        :param channel: Shuttler Core channel to be configured.
        :param offset: Shuttler Core channel offset.
        """
        rtio_output(self.target_base | self.target_offset | channel, offset)

    @kernel
    def get_offset(self, channel):
        """Return the pre-DAC offset value of a Shuttler Core channel.

        :param channel: The Shuttler Core channel.
        :return: Pre-DAC offset value. See :meth:`set_offset`.
        """
        rtio_output(self.target_base | self.target_offset |
            self.target_read | channel, 0)
        return rtio_input_data(self.channel)


class DCBias:
    """Shuttler Core cubic DC-bias spline.

    A Shuttler channel can generate a waveform `w(t)` that is the sum of a
    cubic spline `a(t)` and a sinusoid modulated in amplitude by a cubic
    spline `b(t)` and in phase/frequency by a quadratic spline `c(t)`, where

    .. math::
        w(t) = a(t) + b(t) * cos(c(t))
    
    and `t` corresponds to time in seconds.
    This class controls the cubic spline `a(t)`, in which

    .. math::
        a(t) = p_0 + p_1t + \\frac{p_2t^2}{2} + \\frac{p_3t^3}{6}
    
    and `a(t)` is measured in volts. 

    :param channel: RTIO channel number of this DC-bias spline interface.
    :param core_device: Core device name.
    """
    kernel_invariants = {"core", "channel", "target_o"}

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.target_o = channel << 8

    @kernel
    def set_waveform(self, a0: TInt32, a1: TInt32, a2: TInt64, a3: TInt64):
        """Set the DC-bias spline waveform.

        Given `a(t)` as defined in :class:`DCBias`, the coefficients should be
        configured by the following formulae:

        .. math::
            T &= 8*10^{-9}

            a_0 &= p_0

            a_1 &= p_1T + \\frac{p_2T^2}{2} + \\frac{p_3T^3}{6}

            a_2 &= p_2T^2 + p_3T^3

            a_3 &= p_3T^3
        
        :math:`a_0`, :math:`a_1`, :math:`a_2` and :math:`a_3` are 16, 32, 48
        and 48 bits in width respectively. See :meth:`shuttler_volt_to_mu` for
        machine unit conversion.

        .. note:: 
            The waveform is not updated to the Shuttler Core until
            triggered. See :class:`Trigger` for the update triggering 
            mechanism.

        :param a0: The :math:`a_0` coefficient in machine unit.
        :param a1: The :math:`a_1` coefficient in machine unit.
        :param a2: The :math:`a_2` coefficient in machine unit.
        :param a3: The :math:`a_3` coefficient in machine unit.
        """
        coef_words = [
            a0,
            a1,
            a1 >> 16,
            a2 & 0xFFFF,
            (a2 >> 16) & 0xFFFF,
            (a2 >> 32) & 0xFFFF,
            a3 & 0xFFFF,
            (a3 >> 16) & 0xFFFF,
            (a3 >> 32) & 0xFFFF,
        ]

        for i in range(len(coef_words)):
            rtio_output(self.target_o | i, coef_words[i])
            delay_mu(int64(self.core.ref_multiplier))


class DDS:
    """Shuttler Core DDS spline.

    A Shuttler channel can generate a waveform `w(t)` that is the sum of a
    cubic spline `a(t)` and a sinusoid modulated in amplitude by a cubic
    spline `b(t)` and in phase/frequency by a quadratic spline `c(t)`, where

    .. math::
        w(t) = a(t) + b(t) * cos(c(t))
    
    and `t` corresponds to time in seconds.
    This class controls the cubic spline `b(t)` and quadratic spline `c(t)`,
    in which

    .. math::
        b(t) &= g * (q_0 + q_1t + \\frac{q_2t^2}{2} + \\frac{q_3t^3}{6})

        c(t) &= r_0 + r_1t + \\frac{r_2t^2}{2}
    
    `b(t)` is in volts, `c(t)` is in number of turns. Note that `b(t)`
    contributes to a constant gain of :math:`g=1.64676`.

    :param channel: RTIO channel number of this DC-bias spline interface.
    :param core_device: Core device name.
    """
    kernel_invariants = {"core", "channel", "target_o"}

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.target_o = channel << 8

    @kernel
    def set_waveform(self, b0: TInt32, b1: TInt32, b2: TInt64, b3: TInt64,
            c0: TInt32, c1: TInt32, c2: TInt32):
        """Set the DDS spline waveform.

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
        
        :math:`b_0`, :math:`b_1`, :math:`b_2` and :math:`b_3` are 16, 32, 48
        and 48 bits in width respectively. See :meth:`shuttler_volt_to_mu` for
        machine unit conversion. :math:`c_0`, :math:`c_1` and :math:`c_2` are
        16, 32 and 32 bits in width respectively.

        Note: The waveform is not updated to the Shuttler Core until
        triggered. See :class:`Trigger` for the update triggering mechanism.

        :param b0: The :math:`b_0` coefficient in machine units.
        :param b1: The :math:`b_1` coefficient in machine units.
        :param b2: The :math:`b_2` coefficient in machine units.
        :param b3: The :math:`b_3` coefficient in machine units.
        :param c0: The :math:`c_0` coefficient in machine units.
        :param c1: The :math:`c_1` coefficient in machine units.
        :param c2: The :math:`c_2` coefficient in machine units.
        """
        coef_words = [
            b0,
            b1,
            b1 >> 16,
            b2 & 0xFFFF,
            (b2 >> 16) & 0xFFFF,
            (b2 >> 32) & 0xFFFF,
            b3 & 0xFFFF,
            (b3 >> 16) & 0xFFFF,
            (b3 >> 32) & 0xFFFF,
            c0,
            c1,
            c1 >> 16,
            c2,
            c2 >> 16,
        ]

        for i in range(len(coef_words)):
            rtio_output(self.target_o | i, coef_words[i])
            delay_mu(int64(self.core.ref_multiplier))


class Trigger:
    """Shuttler Core spline coefficients update trigger.

    :param channel: RTIO channel number of the trigger interface.
    :param core_device: Core device name.
    """
    kernel_invariants = {"core", "channel", "target_o"}

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.target_o = channel << 8

    @kernel
    def trigger(self, trig_out):
        """Triggers coefficient update of (a) Shuttler Core channel(s).

        Each bit corresponds to a Shuttler waveform generator core. Setting
        ``trig_out`` bits commits the pending coefficient update (from
        ``set_waveform`` in :class:`DCBias` and :class:`DDS`) to the Shuttler Core
        synchronously.

        :param trig_out: Coefficient update trigger bits. The MSB corresponds
            to Channel 15, LSB corresponds to Channel 0.
        """
        rtio_output(self.target_o, trig_out)


RELAY_SPI_CONFIG = (0*spi.SPI_OFFLINE | 1*spi.SPI_END |
                    0*spi.SPI_INPUT | 0*spi.SPI_CS_POLARITY |
                    0*spi.SPI_CLK_POLARITY | 0*spi.SPI_CLK_PHASE |
                    0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX)

ADC_SPI_CONFIG = (0*spi.SPI_OFFLINE | 0*spi.SPI_END |
                  0*spi.SPI_INPUT | 0*spi.SPI_CS_POLARITY |
                  1*spi.SPI_CLK_POLARITY | 1*spi.SPI_CLK_PHASE |
                  0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX)

# SPI clock write and read dividers
# CS should assert at least 9.5 ns after clk pulse
SPIT_RELAY_WR = 4
# 25 ns high/low pulse hold (limiting for write)
SPIT_ADC_WR = 4
SPIT_ADC_RD = 16

# SPI CS line
CS_RELAY = 1 << 0
CS_LED = 1 << 1
CS_ADC = 1 << 0

# Referenced AD4115 registers
_AD4115_REG_STATUS = 0x00
_AD4115_REG_ADCMODE = 0x01
_AD4115_REG_DATA = 0x04
_AD4115_REG_ID = 0x07
_AD4115_REG_CH0 = 0x10
_AD4115_REG_SETUPCON0 = 0x20


class Relay:
    """Shuttler AFE relay switches.

    This class controls the AFE relay switches and the LEDs. Switch the relay on to
    enable AFE output; off to disable the output. The LEDs indicate the
    relay status.

    .. note::
        The relay does not disable ADC measurements. Voltage of any channels
        can still be read by the ADC even after switching off the relays.

    :param spi_device: SPI bus device name.
    :param core_device: Core device name.
    """
    kernel_invariant = {"core", "bus"}

    def __init__(self, dmgr, spi_device, core_device="core"):
        self.core = dmgr.get(core_device)
        self.bus = dmgr.get(spi_device)
    
    @kernel
    def init(self):
        """Initialize SPI device.

        Configures the SPI bus to 16 bits, write-only, simultaneous relay
        switches and LED control.
        """
        self.bus.set_config_mu(
            RELAY_SPI_CONFIG, 16, SPIT_RELAY_WR, CS_RELAY | CS_LED)

    @kernel
    def enable(self, en: TInt32):
        """Enable/disable relay switches of corresponding channels.

        Each bit corresponds to the relay switch of a channel. Asserting a bit
        turns on the corresponding relay switch; deasserting the same bit
        turns off the switch instead.

        :param en: Switch enable bits. The MSB corresponds to Channel 15, LSB
            corresponds to Channel 0.
        """
        self.bus.write(en << 16)


class ADC:
    """Shuttler AFE ADC (AD4115) driver.

    :param spi_device: SPI bus device name.
    :param core_device: Core device name.
    """
    kernel_invariant = {"core", "bus"}

    def __init__(self, dmgr, spi_device, core_device="core"):
        self.core = dmgr.get(core_device)
        self.bus = dmgr.get(spi_device)

    @kernel
    def read_id(self) -> TInt32:
        """Read the product ID of the ADC.

        The expected return value is 0x38DX, the 4 LSbs are don't cares.

        :return: The read-back product ID.
        """
        return self.read16(_AD4115_REG_ID)

    @kernel
    def reset(self):
        """AD4115 reset procedure.

        Performs a write operation of 96 serial clock cycles with DIN
        held at high. This resets the entire device, including the register
        contents.

        .. note::
            The datasheet only requires 64 cycles, but reasserting ``CS_n`` right
            after the transfer appears to interrupt the start-up sequence.
        """
        self.bus.set_config_mu(ADC_SPI_CONFIG, 32, SPIT_ADC_WR, CS_ADC)
        self.bus.write(0xffffffff)
        self.bus.write(0xffffffff)
        self.bus.set_config_mu(
            ADC_SPI_CONFIG | spi.SPI_END, 32, SPIT_ADC_WR, CS_ADC)
        self.bus.write(0xffffffff)

    @kernel
    def read8(self, addr: TInt32) -> TInt32:
        """Read from 8-bit register.

        :param addr: Register address.
        :return: Read-back register content.
        """
        self.bus.set_config_mu(
            ADC_SPI_CONFIG | spi.SPI_END | spi.SPI_INPUT,
            16, SPIT_ADC_RD, CS_ADC)
        self.bus.write((addr | 0x40) << 24)
        return self.bus.read() & 0xff

    @kernel
    def read16(self, addr: TInt32) -> TInt32:
        """Read from 16-bit register.

        :param addr: Register address.
        :return: Read-back register content.
        """
        self.bus.set_config_mu(
            ADC_SPI_CONFIG | spi.SPI_END | spi.SPI_INPUT,
            24, SPIT_ADC_RD, CS_ADC)
        self.bus.write((addr | 0x40) << 24)
        return self.bus.read() & 0xffff

    @kernel
    def read24(self, addr: TInt32) -> TInt32:
        """Read from 24-bit register.

        :param addr: Register address.
        :return: Read-back register content.
        """
        self.bus.set_config_mu(
            ADC_SPI_CONFIG | spi.SPI_END | spi.SPI_INPUT,
            32, SPIT_ADC_RD, CS_ADC)
        self.bus.write((addr | 0x40) << 24)
        return self.bus.read() & 0xffffff

    @kernel
    def write8(self, addr: TInt32, data: TInt32):
        """Write to 8-bit register.

        :param addr: Register address.
        :param data: Data to be written.
        """
        self.bus.set_config_mu(
            ADC_SPI_CONFIG | spi.SPI_END, 16, SPIT_ADC_WR, CS_ADC)
        self.bus.write(addr << 24 | (data & 0xff) << 16)

    @kernel
    def write16(self, addr: TInt32, data: TInt32):
        """Write to 16-bit register.

        :param addr: Register address.
        :param data: Data to be written.
        """
        self.bus.set_config_mu(
            ADC_SPI_CONFIG | spi.SPI_END, 24, SPIT_ADC_WR, CS_ADC)
        self.bus.write(addr << 24 | (data & 0xffff) << 8)

    @kernel
    def write24(self, addr: TInt32, data: TInt32):
        """Write to 24-bit register.

        :param addr: Register address.
        :param data: Data to be written.
        """
        self.bus.set_config_mu(
            ADC_SPI_CONFIG | spi.SPI_END, 32, SPIT_ADC_WR, CS_ADC)
        self.bus.write(addr << 24 | (data & 0xffffff))

    @kernel
    def read_ch(self, channel: TInt32) -> TFloat:
        """Sample a Shuttler channel on the AFE.

        Performs a single conversion using profile 0 and setup 0 on the
        selected channel. The sample is then recovered and converted to volts.

        :param channel: Shuttler channel to be sampled.
        :return: Voltage sample in volts.
        """
        # Always configure Profile 0 for single conversion
        self.write16(_AD4115_REG_CH0, 0x8000 | ((channel * 2 + 1) << 4))
        self.write16(_AD4115_REG_SETUPCON0, 0x1300)
        self.single_conversion()

        delay(100*us)
        adc_code = self.read24(_AD4115_REG_DATA)
        return ((adc_code / (1 << 23)) - 1) * 2.5 / 0.1
    
    @kernel
    def single_conversion(self):
        """Place the ADC in single conversion mode.

        The ADC returns to standby mode after the conversion is complete.
        """
        self.write16(_AD4115_REG_ADCMODE, 0x8010)

    @kernel
    def standby(self):
        """Place the ADC in standby mode and disable power down the clock.

        The ADC can be returned to single conversion mode by calling
        :meth:`single_conversion`.
        """
        # Selecting internal XO (0b00) also disables clock during standby
        self.write16(_AD4115_REG_ADCMODE, 0x8020)

    @kernel
    def power_down(self):
        """Place the ADC in power-down mode.

        The ADC must be reset before returning to other modes.
        
        .. note::
            The AD4115 datasheet suggests placing the ADC in standby mode
            before power-down. This is to prevent accidental entry into the
            power-down mode. See also :meth:`standby` and :meth:`power_up`.
        """
        self.write16(_AD4115_REG_ADCMODE, 0x8030)

    @kernel
    def power_up(self):
        """Exit the ADC power-down mode.
        
        The ADC should be in power-down mode before calling this method.

        See also :meth:`power_down`.
        """
        self.reset()
        # Although the datasheet claims 500 us reset wait time, only waiting
        # for ~500 us can result in DOUT pin stuck in high
        delay(2500*us)

    @kernel
    def calibrate(self, volts, trigger, config, samples=[-5.0, 0.0, 5.0]):
        """Calibrate the Shuttler waveform generator using the ADC on the AFE.

        Finds the average slope rate and average offset by samples, and
        compensates by writing the pre-DAC gain and offset registers in the
        configuration registers.

        .. note::
            If the pre-calibration slope rate is less than 1, the calibration 
            procedure will introduce a pre-DAC gain compensation. However, this 
            may saturate the pre-DAC voltage code (see :class:`Config` notes).
            Shuttler cannot cover the entire +/- 10 V range in this case.
            See also :meth:`Config.set_gain` and :meth:`Config.set_offset`.

        :param volts: A list of all 16 cubic DC-bias splines.
            (See :class:`DCBias`)
        :param trigger: The Shuttler spline coefficient update trigger.
        :param config: The Shuttler Core configuration registers.
        :param samples: A list of sample voltages for calibration. There must
            be at least 2 samples to perform slope rate calculation.
        """
        assert len(volts) == 16
        assert len(samples) > 1

        measurements = [0.0] * len(samples)

        for ch in range(16):
            # Find the average slope rate and offset
            for i in range(len(samples)):
                self.core.break_realtime()
                volts[ch].set_waveform(
                    shuttler_volt_to_mu(samples[i]), 0, 0, 0)
                trigger.trigger(1 << ch)
                measurements[i] = self.read_ch(ch)

            # Find the average output slope
            slope_sum = 0.0
            for i in range(len(samples) - 1):
                slope_sum += (measurements[i+1] - measurements[i])/(samples[i+1] - samples[i])
            slope_avg = slope_sum / (len(samples) - 1)

            gain_code = int32(1 / slope_avg * (2 ** 16)) & 0xffff

            # Scale the measurements by 1/slope, find average offset
            offset_sum = 0.0
            for i in range(len(samples)):
                offset_sum += (measurements[i] / slope_avg) - samples[i]
            offset_avg = offset_sum / len(samples)

            offset_code = shuttler_volt_to_mu(-offset_avg)

            self.core.break_realtime()
            config.set_gain(ch, gain_code)

            delay_mu(int64(self.core.ref_multiplier))
            config.set_offset(ch, offset_code)
