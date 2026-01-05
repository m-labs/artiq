from numpy import int32, int64

from artiq.coredevice.rtio import rtio_output, rtio_input_data
from artiq.language.core import *
from artiq.language.types import *
from artiq.language.units import us, ns

PHASER_GW_VARIANT_MTDDS = 1

PHASER_REG_MAP = [
    HW_VARIANT,
    GW_VARIANT,
    SAMPLE_PER_CYCLE,
    AVAILABLE_TONES,
    DAC_CTRL_ADDR,
    DAC_STATUS_ADDR,
    DAC_SOURCE_SEL_ADDR,
    DAC_TEST_WORD_0_I_ADDR,
    DAC_TEST_WORD_0_Q_ADDR,
    DAC_TEST_WORD_1_I_ADDR,
    DAC_TEST_WORD_1_Q_ADDR,
    ATT_RESET_N,
    TRF_PS,
    TRF_LOCK_DETECT,
    ADC_DATA,
    ADC_GAIN,
] = range(16)

PHASER_SERVO_PROFILES = 4
PHASER_SERVO_REG_MAP = [
    SERVO_ADC_SOURCE_SEL,
    SERVO_PROFILE_SEL,
    SERVO_ENABLE,
    SERVO_CLIPPED,
] = range(4)


class _DummyIQUpconverter:
    def __init__(self):
        self.use_external_lo = False

    @portable
    def init(self):
        pass


class PhaserMTDDS:
    """Phaser FPGA and DAC DAC34H84 configuration interface.

    :param sysclk: Sysclk frequency
    :param dac_device: DAC device name.
    :param core_device: Core device name (default: "core").

    Attributes:

    * :attr:`dac`: A :class:`DAC34H84<artiq.coredevice.dac34h84.DAC34H84>`.

    """

    kernel_invariants = {
        "core",
        "channel",
        "dac",
        "samples_per_cycle",
        "target_write",
        "target_read",
    }

    def __init__(
        self,
        dmgr,
        channel,
        sysclk,
        dac_device,
        core_device="core",
    ):
        self.channel = channel
        self.core = dmgr.get(core_device)
        self.dac = dmgr.get(dac_device)

        self.samples_per_cycle = int(self.dac.input_sample_rate / sysclk)

        self.target_write = self.channel << 8
        self.target_read = (
            self.channel << 8 | 1 << (len(PHASER_REG_MAP) - 1).bit_length()
        )

        self.gain_mus = [0b00, 0b00]

    @staticmethod
    def get_rtio_channels(channel_base, **kwargs):
        return [(channel_base, "base")]

    @kernel
    def init(self):
        """Initialize the Phaser.

        Verify the gateware variant, initialize and test the DAC.
        """
        if self.read(GW_VARIANT) != PHASER_GW_VARIANT_MTDDS:
            raise ValueError("PhaserMTDDS gateware variant mismatch")
        delay(40.0 * us)
        if self.read(SAMPLE_PER_CYCLE) != self.samples_per_cycle:
            raise ValueError("PhaserMTDDS samples per cycle (DDS bandwidth) mismatch")
        delay(40.0 * us)

        # Toggle reset and keep tx off
        self.set_dac_ctrl(txena=False, reset=True, sleep=False)
        self.set_dac_ctrl(txena=False, reset=False, sleep=False)
        delay(10.0 * us) # slack

        self.dac.init()

        test_patterns = [
            [
                0x7A7A,
                0xB6B6,
                0xEAEA,
                0x4545,
            ],  # datasheet test word pattern a - SLAS751D Table 37-40
            [
                0x1A1A,
                0x1616,
                0xAAAA,
                0xC6C6,
            ],  # datasheet test word pattern b - SLAS751D Table 41-44
        ]
        for p in test_patterns:
            self.test_dac(p)

        # enable DAC tx
        self.set_dac_ctrl(txena=True, reset=False, sleep=False)

    @kernel
    def write(self, address, data):
        rtio_output(self.target_write | address, data)

    @kernel
    def read(self, address):
        rtio_output(self.target_read | address, 0)
        return rtio_input_data(self.channel)

    @kernel
    def reset_attenuator(self, channel):
        reg = self.read(ATT_RESET_N)
        delay(40.0 * us)
        self.write(ATT_RESET_N, reg & ~(1 << channel))
        delay_mu(int64(self.core.ref_multiplier))
        self.write(ATT_RESET_N, reg | 1 << channel)
        delay_mu(int64(self.core.ref_multiplier))

    @kernel
    def is_upconverter_variant(self) -> TBool:
        is_upconverter = self.read(HW_VARIANT) == 0
        return is_upconverter

    @kernel
    def upconverter_pll_locked(self, channel) -> TBool:
        """Return True when the upconverter PLL locks and False when the PLL unlocks

        This method consumes all slack.

        :param channel: Phaser channel number (0 or 1)
        """
        locked = (self.read(TRF_LOCK_DETECT) >> channel) & 0b1 == 0b1
        return locked

    @kernel
    def get_available_tones(self) -> TInt32:
        tones = self.read(AVAILABLE_TONES)
        return tones

    @kernel
    def select_dac_source(self, channel, source):
        """Select the input source of the DAC34H84

        * When source = 0, :math:`\\text{DAC[channel]} = \\text{TEST WORD I} + j (\\text{TEST WORD J})`
        * When source = 1, :math:`\\text{DAC[channel]} = A_1 (\\cos{\\theta_1} + j \\sin{\\theta_1}) + A_2 (\\cos{\\theta_2} + j \\sin{\\theta_2}) + ...`
        * When source = 2, :math:`\\text{DAC[channel]} = y\\text{[channel]} (A_1 (\\cos{\\theta_1} + j \\sin{\\theta_1}) + A_2 (\\cos{\\theta_2} + j \\sin{\\theta_2}) + ... )`

        Where:
            * :math:`y`: Servo IIR output
            * :math:`A`: DDS amplitude
            * :math:`\\theta`: DDS phase

        :param channel: Phaser channel number (0 or 1)
        :param source: 2-bit source select register (set to 0 for test word, 1 for DDSs, 2 for Servo)
        """
        reg = self.read(DAC_SOURCE_SEL_ADDR)
        delay(40.0 * us)
        self.write(
            DAC_SOURCE_SEL_ADDR,
            (reg & ~(0b11 << (2 * channel))) | (source & 0b11) << (2 * channel),
        )
        delay_mu(int64(self.core.ref_multiplier))

    @kernel
    def set_dac_ctrl(self, txena, reset, sleep):
        """Set DAC34H84 control register.

        :param txena: Enable DAC34H84 TX when set to True
        :param reset: Reset DAC34H84 when set to True
        :param sleep: Power down DAC34H84 when set to True
        """
        reg = 0
        if txena:
            reg |= 1
        if not reset:
            # bit1 = resetb
            reg |= 1 << 1
        if sleep:
            reg |= 1 << 2
        self.write(DAC_CTRL_ADDR, reg)
        delay_mu(int64(self.core.ref_multiplier))

    @kernel
    def test_dac(self, pattern):
        """Start DAC34H84 iotest via internal data pattern checker

        :param pattern: a list of 16-bit test words
        """
        if len(pattern) != 4:
            raise ValueError("pattern length mismatch")

        test_word_addr = [
            DAC_TEST_WORD_0_I_ADDR,
            DAC_TEST_WORD_0_Q_ADDR,
            DAC_TEST_WORD_1_I_ADDR,
            DAC_TEST_WORD_1_Q_ADDR,
        ]

        for i in range(len(pattern)):
            # repeat the pattern twice
            self.dac.write(0x25 + i, pattern[i])
            self.dac.write(0x29 + i, pattern[i])
            self.write(test_word_addr[i], pattern[i])
            delay_mu(int64(self.core.ref_multiplier))

        # start writing test words to DAC
        self.select_dac_source(0, 0)
        self.select_dac_source(1, 0)

        reg_0x01 = self.dac.read(0x01)
        delay(40.0 * us)
        # enable iotest & clear iotest_result
        self.dac.write(0x01, reg_0x01 | 0x8000)
        self.dac.write(0x04, 0x0000)

        # let it run for a while
        delay(100.0 * us)

        iotest_error = self.dac.read(0x04)
        delay(40.0 * us)
        if iotest_error != 0:
            raise ValueError("DAC iotest failure")

        # disable iotest
        self.dac.write(0x01, reg_0x01)

        # stop writing test words to DAC
        self.select_dac_source(0, 1)
        self.select_dac_source(1, 1)

    @kernel
    def set_pgia(self, adc_channel, gain):
        """Set instrumentation amplifier gain of an ADC channel.

        :param adc_channel: Phaser ADC channel number (0 or 1)
        :param gain: Amplifier gain (1, 10, 100 or 1000)
        """
        if gain == 1:
            gain_mu = 0b00
        elif gain == 10:
            gain_mu = 0b01
        elif gain == 100:
            gain_mu = 0b10
        elif gain == 1000:
            gain_mu = 0b11
        else:
            raise ValueError("Invalid gain")
        self.gain_mus[adc_channel] = gain_mu
        reg = self.read(ADC_GAIN)
        delay(40.0 * us)
        self.write(
            ADC_GAIN,
            (reg & ~(0b11 << (2 * adc_channel)))
            | (gain_mu & 0b11) << (2 * adc_channel),
        )

    @portable(flags={"fast-math"})
    def adc_mu_to_volt(self, data, gain) -> TFloat:
        if data & (1 << 15) != 0:
            data = data - (1 << 16)
        return (4.096 * data / 0x7FFF) * (5 / 2) / (10 ** (gain))

    @kernel
    def get_adc_mu(self, channel) -> TInt32:
        """Return the latest ADC reading in machine units.

        This method consumes all slack.

        :param channel: Phaser ADC channel number (0 or 1)
        :return: 16-bit signed ADC sample in machine unit
        """
        data = self.read(ADC_DATA)
        if channel == 0:
            return data & 0xFFFF
        else:
            return (data >> 16) & 0xFFFF

    @kernel
    def get_adc(self, channel) -> TFloat:
        """Return the latest ADC reading in SI units.

        This method consumes all slack.

        :param channel: Phaser ADC channel number (0 or 1)
        :return: ADC sample in Volt
        """
        return self.adc_mu_to_volt(self.get_adc_mu(channel), self.gain_mus[channel])


class PhaserMTDDSChannel:
    """Phaser channel with IQ multitone DDS.

    This class supports a channel with multiple IQ DDSs and exposes the channel devices:

    * baseband hardware variant: multitone DDSs and digital step attenuator
    * upconverter hardware variant: multitone DDSs, digital step attenuator and upconverter

    .. note:: Due to hardware limitation, it's not possible to use external LO in channel 1 upconverter and use internal VCO in channel 0 upconverter.
              As the upconverter external LO input in channel 1 is directly connected to the upconverter LO output in channel 0.

    :param tones: Total number of IQ DDSs
    :param fpga_device: Phaser FPGA device name.
    :param dac_device: DAC device name.
    :param att_device: Attenuator device name.
    :param dds_device_prefix: Phaser IQ DDS device name prefix.
    :param iquc_device: Upconverter device name (defualt: None)
    :param core_device: Core device name (default: "core").

    Attributes:

    * :attr:`attenuator`: A :class:`HMC542B<artiq.coredevice.hmc542b.HMC542B>`.
    * :attr:`upconverter`: A :class:`TRF372017<artiq.coredevice.trf372017.TRF372017>` if ``iquc_device`` is provided.
    * :attr:`servo`: A :class:`PhaserServo`.
    * :attr:`ddss`: List of :class:`PhaserDDS`.

    """

    kernel_invariants = {
        "core",
        "channel_index",
        "tones",
        "fpga",
        "dac",
        "attenuator",
        "servo",
        "has_upconverter",
        "upconverter",
        "ddss",
    }

    def __init__(
        self,
        dmgr,
        channel_index,
        tones,
        fpga_device,
        dac_device,
        att_device,
        servo_device,
        dds_device_prefix,
        iquc_device=None,
        core_device="core",
    ):
        self.core = dmgr.get(core_device)
        self.channel_index = channel_index
        self.tones = tones

        self.fpga = dmgr.get(fpga_device)
        self.dac = dmgr.get(dac_device)
        self.attenuator = dmgr.get(att_device)
        self.servo = dmgr.get(servo_device)

        if iquc_device is None:
            self.upconverter = _DummyIQUpconverter()
            self.has_upconverter = False
        else:
            self.upconverter = dmgr.get(iquc_device)
            self.has_upconverter = True
        self.ddss = [dmgr.get(dds_device_prefix + str(i)) for i in range(tones)]

    @kernel
    def init(self):
        """Initialize the Phaser channel.

        Verify the number of tones and hardware variant, reset attenuators and initialize upconverter if available.
        """
        if self.fpga.get_available_tones() != self.tones:
            raise ValueError("PhaserMTDDS number of available tones mismatch")
        delay(40.0 * us)
        if self.has_upconverter != self.fpga.is_upconverter_variant():
            raise ValueError("PhaserMTDDS hardware variant mismatch")
        delay(40.0 * us)

        self.fpga.reset_attenuator(self.channel_index)
        delay(10.0 * us) # slack

        if self.has_upconverter:
            self.upconverter.init()

            # SLWS224E datasheet didn't mention any PLL lock time, 500 us should be enough
            delay(500 * us)

            # External LO doesn't use PLL, no need to check lock status
            if not (self.upconverter.use_external_lo or self.upconverter_pll_locked()):
                raise ValueError("TRF372017 PLL fails to lock")
            delay(40.0 * us)

    @kernel
    def upconverter_pll_locked(self) -> TBool:
        """Returns whether the upconverter PLL is locked

        This method consumes all slack.

        See also :meth:`PhaserMTDDS.upconverter_pll_locked`

        """
        if self.upconverter.use_external_lo: 
            raise ValueError("External LO is used and PLL is bypassed")
        return self.fpga.upconverter_pll_locked(self.channel_index)

    @kernel
    def stage_dac_nco_mixer_frequency_mu(self, ftw):
        """Stage the DAC NCO mixer frequency in machine units.

        Before using DAC NCO mixer, the mixer must be enabled via :meth:`DAC34H84.enable_mixer<artiq.coredevice.dac34h84.DAC34H84.enable_mixer>`.
        The settings is only applied after triggering DAC synchronisation via :meth:`DAC34H84.sync<artiq.coredevice.dac34h84.DAC34H84.sync>`.

        See also :meth:`DAC34H84.stage_nco_mixer_frequency_mu<artiq.coredevice.dac34h84.DAC34H84.stage_nco_mixer_frequency_mu>`

        :param ftw: 32-bit NCO frequency tuning word
        """
        self.dac.stage_nco_mixer_frequency_mu(self.channel_index, ftw)

    @kernel
    def stage_dac_nco_mixer_phase_offset_mu(self, pow):
        """Stage the DAC NCO mixer phase offset in machine units.

        Before using DAC NCO mixer, the mixer must be enabled via :meth:`DAC34H84.enable_mixer<artiq.coredevice.dac34h84.DAC34H84.enable_mixer>`.
        The settings is only applied after triggering DAC synchronisation via :meth:`DAC34H84.sync<artiq.coredevice.dac34h84.DAC34H84.sync>`.

        See also :meth:`DAC34H84.stage_nco_mixer_phase_offset_mu<artiq.coredevice.dac34h84.DAC34H84.stage_nco_mixer_phase_offset_mu>`

        :param ftw: 16-bit NCO phase offset word
        """
        self.dac.stage_nco_mixer_phase_offset_mu(self.channel_index, pow)

    @kernel
    def stage_dac_nco_mixer_frequency(self, frequency):
        """Stage the DAC NCO mixer frequency in SI units.

        Before using DAC NCO mixer, the mixer must be enabled via :meth:`DAC34H84.enable_mixer<artiq.coredevice.dac34h84.DAC34H84.enable_mixer>`.
        The settings is only applied after triggering DAC synchronisation via :meth:`DAC34H84.sync<artiq.coredevice.dac34h84.DAC34H84.sync>`.

        See also :meth:`DAC34H84.stage_nco_mixer_frequency<artiq.coredevice.dac34h84.DAC34H84.stage_nco_mixer_frequency>`

        :param frequency: NCO frequency in Hz (-500 MHz to +500 MHz)
        """
        self.dac.stage_nco_mixer_frequency(self.channel_index, frequency)

    @kernel
    def stage_dac_nco_mixer_phase_offset(self, phase):
        """Stage the DAC NCO mixer phase offset in SI units.

        Before using DAC NCO mixer, the mixer must be enabled via :meth:`DAC34H84.enable_mixer<artiq.coredevice.dac34h84.DAC34H84.enable_mixer>`.
        The settings is only applied after triggering DAC synchronisation via :meth:`DAC34H84.sync<artiq.coredevice.dac34h84.DAC34H84.sync>`.

        See also :meth:`DAC34H84.stage_nco_mixer_phase_offset<artiq.coredevice.dac34h84.DAC34H84.stage_nco_mixer_phase_offset>`

        :param phase: NCO phase offset in turns (0.0 to 1.0)
        """
        self.dac.stage_nco_mixer_phase_offset(self.channel_index, phase)

    @kernel
    def select_dac_source(self, source):
        """Select the input source of the DAC34H84

        See also :meth:`PhaserMTDDS.select_dac_source`

        :param source: 2-bit source select register (set to 0 for test word, 1 for DDSs, 2 for Servo)
        """
        self.fpga.select_dac_source(self.channel_index, source)


class PhaserDDS:
    """Phaser IQ DDS driver

    :param bandwidth: DDS bandwidth
    :param core_device: Core device name (default: "core").
    """

    kernel_invariants = {"core", "channel"}

    def __init__(self, dmgr, channel, bandwidth, core_device="core"):
        self.channel = channel
        self.core = dmgr.get(core_device)

        self.bandwidth = bandwidth
        self.target_ftw = (self.channel << 8) | 0
        self.target_pow = (self.channel << 8) | 1
        self.target_asf = (self.channel << 8) | 2
        self.target_clear = (self.channel << 8) | 3

    @staticmethod
    def get_rtio_channels(channel_base, **kwargs):
        return [(channel_base, "channel")]

    @kernel
    def set_frequency_mu(self, ftw):
        """Set the DDS frequency in machine units.

        :param ftw: 32-bit DDS frequency tuning word
        """
        rtio_output(self.target_ftw, ftw)

    @kernel
    def set_phase_offset_mu(self, pow):
        """Set the DDS phase offset in machine units.

        :param ftw: 16-bit DDS phase offset word
        """
        rtio_output(self.target_pow, pow)

    @kernel
    def set_amplitude_mu(self, asf):
        """Set the DDS amplitude in machine units.

        :param ftw: 16-bit DDS amplitude scale factor
        """
        rtio_output(self.target_asf, asf)

    @portable(flags={"fast-math"})
    def frequency_to_ftw(self, frequency) -> TInt32:
        """Return the 32-bit frequency tuning word corresponding to the given frequency in Hz."""
        return int32(round((int64(1) << 32) * (frequency / self.bandwidth)))

    @portable(flags={"fast-math"})
    def turns_to_pow(self, turns) -> TInt32:
        """Return the 16-bit phase offset word corresponding to the given phase in turns."""
        return int32(round(turns * (1 << 16)))

    @portable(flags={"fast-math"})
    def amplitude_to_asf(self, amplitude) -> TInt32:
        """Return the 16-bit amplitude scale factor corresponding to the given fractional amplitude."""
        return int32(round(amplitude * ((1 << 15) - 1)))

    @kernel
    def set_frequency(self, frequency):
        """Set the DDS frequency in SI units.

        Due to different DAC interpolation ratio between DDS bandwidth, the resulting frequency responses are different between bandwidths:

        * 250 MHz DDS bandwidth: passband from -100 MHz to +100 MHz, wrapping around at ±125 MHz
        * 500 MHz DDS bandwidth: passband from -200 MHz to +200 MHz, wrapping around at ±250 MHz

        :param frequency: DDS frequency in Hz
        """
        self.set_frequency_mu(self.frequency_to_ftw(frequency))

    @kernel
    def set_phase_offset(self, phase):
        """Set the DDS phase offset in SI units.

        :param phase: DDS phase offset in turns (0.0 to 1.0)
        """
        self.set_phase_offset_mu(self.turns_to_pow(phase))

    @kernel
    def set_amplitude(self, amplitude):
        """Set the DDS amplitude in SI units.

        :param amplitude: DDS amplitude (-1.0 to 1.0)
        """
        self.set_amplitude_mu(self.amplitude_to_asf(amplitude))

    @kernel
    def enable_phase_accumulator(self, enable):
        """Enable/disable the DDS phase accmulator.

        When the phase accmulator is disabled, the phase value is set to zero.
        Otherwise, the frequency tuning word is added to the accmulator at each clock cycle.

        :param enable: Enable the DDS phase accmulator if True
        """
        rtio_output(self.target_clear, 0 if enable else 1)


class PhaserServo:
    """Phaser Servo driver

    :param core_device: Core device name (default: "core").
    """

    kernel_invariants = {
        "core",
        "channel",
        "addr_offset",
        "target_write",
        "target_read",
    }

    def __init__(self, dmgr, channel, core_device="core"):
        self.channel = channel
        self.core = dmgr.get(core_device)

        self.addr_offset = len(PHASER_SERVO_REG_MAP)
        self.target_write = self.channel << 8
        self.target_read = (
            self.channel << 8
            | 1 << (self.addr_offset + PHASER_SERVO_PROFILES * 6 - 1).bit_length()
        )

    @staticmethod
    def get_rtio_channels(channel_base, **kwargs):
        return [(channel_base, "channel")]

    @kernel
    def write(self, address, data):
        rtio_output(self.target_write | address, data)

    @kernel
    def read(self, address):
        rtio_output(self.target_read | address, 0)
        return rtio_input_data(self.channel)

    @portable(flags={"fast-math"})
    def setpoint_to_offset(self, setpoint) -> TInt32:
        """Return the 16-bit IIR offset corresponding to the given fractional setpoint."""
        return int32(round(setpoint * ((1 << 15) - 1)))

    @portable(flags={"fast-math"})
    def full_scale_to_y_mu(self, y) -> TInt32:
        """Return the 16-bit IIR y filter output corresponding to the given fractional filter output."""
        return int32(round(y * ((1 << 15) - 1)))

    @portable(flags={"fast-math"})
    def y_mu_to_full_scale(self, y_mu) -> TFloat:
        """Return the fractional filter output to the given 16-bit IIR y filter output."""
        return y_mu / ((1 << 15) - 1)

    @portable(flags={"fast-math"})
    def pi_to_iir_mu(self, kp, ki=0.0, g=0.0):
        """Return the IIR coefficients to the given Proportional–Integral (PI) controller.

        The PI controller transfer function is:

        .. math::
            H(s) = k_p + \\frac{k_i}{s + \\frac{k_i}{g}}

        Where:
            * :math:`s = \\sigma + i\\omega` is the complex frequency
            * :math:`k_p` is the proportional gain
            * :math:`k_i` is the integrator gain
            * :math:`g` is the integrator gain limit


        The IIR recurrence relation is:

        .. math::
            a_0 \\times y[n] = b_0 (x[n] + o) + b_1 (x[n-1] + o) + a_1 \\times y[n-1]

        Where:
            * :math:`y`: 16-bit output signal
            * :math:`x`: 16-bit input signal
            * :math:`o`: 16-bit offset
            * :math:`b_0`, :math:`a_1`, :math:`b_1`: 18-bit filter coefficients
            * :math:`a_0`: a constant filter coefficient, :math:`a_0 = 1 << 11`

        :param kp: Proportional gain.
        :param ki: Integrator gain (rad/s). When 0 (the default)
            this implements a pure P controller. Same sign as ``kp``.
        :param g: Integrator gain limit. When 0 (the default) the
            integrator gain limit is infinite. Same sign as ``ki``.
        :return: A tuple (b0, a1, b1)
        """
        NORM = 1 << 11
        COEFF_LIMIT = 1 << 17  # 18-bit filter coefficients
        T_CYCLE = 208 * ns  # 4.8 MSPS ADC sample rate

        # Bilinear transform is used to convert the transfer function to a first order IIR.
        if ki == 0.0:
            # pure P
            a1 = 0
            b1 = 0
            b0 = int(round(kp * NORM))
        else:
            # I or PI
            ki = ki * (T_CYCLE / 2.0)
            if g == 0.0:
                c = 1.0
                a1 = NORM
            else:
                c = 1.0 / (1.0 + ki / g)
                a1 = int(round((2.0 * c - 1.0) * NORM))
            b0 = int(round((kp + ki * c) * NORM))
            b1 = int(round((kp + (ki - 2.0 * kp) * c) * NORM))
            if b1 == -b0:
                raise ValueError("integrator gain and/or gain limit too low")

        if (
            b0 >= COEFF_LIMIT
            or b0 < -COEFF_LIMIT
            or b1 >= COEFF_LIMIT
            or b1 < -COEFF_LIMIT
        ):
            raise ValueError("gains too high")

        return b0, a1, b1

    @kernel
    def set_iir(self, profile, setpoint, kp, ki=0.0, g=0.0):
        """Set a profile's IIR coefficients.

        .. warning:: The coefficients update are applied sequentially. To apply a synchronous change, use a different profile as buffer or disable the IIR before writing to the active profile.

        See also :meth:`PhaserServo.pi_to_iir_mu`

        :param profile: Profile number (0 to 3)
        :param setpoint: fractional setpoint (0.0 to 1.0)
        :param kp: Proportional gain.
        :param ki: Integrator gain (rad/s). When 0 (the default)
            this implements a pure P controller. Same sign as ``kp``.
        :param g: Integrator gain limit. When 0 (the default) the
            integrator gain limit is infinite. Same sign as ``ki``.
        """
        b0, a1, b1 = self.pi_to_iir_mu(kp, ki, g)
        self.set_iir_mu(profile, self.setpoint_to_offset(setpoint), b0, a1, b1)

    @kernel
    def set_iir_mu(self, profile, offset, b0, a1, b1):
        """Set a profile's IIR coefficients in machine unit.

        This method advances the timeline by four coarse RTIO clock cycles.

        .. warning:: The coefficients update are applied sequentially. To apply a synchronous change, use a different profile as buffer or disable the IIR before writing to the active profile.

        See also :meth:`PhaserServo.pi_to_iir_mu` for the IIR recurrence relation.

        :param profile: Profile number (0 to 3)
        :param offset: 16-bit signed offset
        :param b0: 18-bit signed coefficient
        :param a1: 18-bit signed coefficient
        :param b1: 18-bit signed coefficient
        """
        profile_addr = self.addr_offset + profile * 6
        self.write(profile_addr + 0, b0)
        delay_mu(int64(self.core.ref_multiplier))
        self.write(profile_addr + 1, a1)
        delay_mu(int64(self.core.ref_multiplier))
        self.write(profile_addr + 2, b1)
        delay_mu(int64(self.core.ref_multiplier))
        self.write(profile_addr + 3, offset)
        delay_mu(int64(self.core.ref_multiplier))

    @kernel
    def iir_output_clipped(self) -> TBool:
        """Returns whether the IIR output is clipped

        This method consumes all slack.
        """
        return self.read(SERVO_CLIPPED) != 0

    @kernel
    def set_y1_mu(self, profile, y1):
        """Set a profile's IIR y[n-1] in machine unit.

        :param profile: Profile number (0 to 3)
        :param y1: 16-bit signed y[n-1] filter output
        """
        profile_addr = self.addr_offset + profile * 6
        self.write(profile_addr + 5, y1)
        delay_mu(int64(self.core.ref_multiplier))

    @kernel
    def get_y1_mu(self, profile) -> TInt32:
        """Return a profile's IIR y[n-1] in machine unit.

        This method consumes all slack.

        :param profile: Profile number (0 to 3)
        :return: 16-bit signed y[n-1] filter output
        """
        profile_addr = self.addr_offset + profile * 6
        return self.read(profile_addr + 5)

    @kernel
    def set_y1(self, profile, y1):
        """Set a profile's IIR y[n-1].

        :param profile: Profile number (0 to 3)
        :param y1: fractional y[n-1] filter output (-1.0 to 1.0)
        """
        self.set_y1_mu(profile, self.full_scale_to_y_mu(y1))

    @kernel
    def get_y1(self, profile) -> TFloat:
        """Return a profile's IIR y[n-1].

        This method consumes all slack.

        :param profile: Profile number (0 to 3)
        :return: fractional y[n-1] filter output
        """
        return self.y_mu_to_full_scale(self.get_y1_mu(profile))

    @kernel
    def enable_iir(self, enable):
        """Enable/disable the IIR.

        :param enable: Enable the IIR if True
        """
        self.write(SERVO_ENABLE, 1 if enable else 0)
        delay_mu(int64(self.core.ref_multiplier))

    @kernel
    def set_active_profile(self, profile):
        """Set the active profile used by the IIR.

        :param profile: Profile number (0 to 3)
        """
        self.write(SERVO_PROFILE_SEL, profile)
        delay_mu(int64(self.core.ref_multiplier))

    @kernel
    def select_iir_source(self, adc_channel):
        """Select the ADC channel to be the input source of the IIR.

        :param adc_channel: Phaser ADC channel number (0 or 1)
        """
        self.write(SERVO_ADC_SOURCE_SEL, adc_channel)
        delay_mu(int64(self.core.ref_multiplier))
