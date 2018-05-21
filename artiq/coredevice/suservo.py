from artiq.language.core import kernel, delay, now_mu, delay_mu
from artiq.language.units import us, ns
from artiq.coredevice.rtio import rtio_output, rtio_input_data
from artiq.coredevice import spi2 as spi
from artiq.coredevice import urukul, sampler


COEFF_WIDTH = 18
COEFF_DEPTH = 10 + 1
WE = 1 << COEFF_DEPTH + 1
STATE_SEL = 1 << COEFF_DEPTH
CONFIG_SEL = 1 << COEFF_DEPTH - 1
CONFIG_ADDR = CONFIG_SEL | STATE_SEL
T_CYCLE = (2*(8 + 64) + 2 + 1)*8*ns
COEFF_SHIFT = 11


class SUServo:
    """Sampler-Urukul Servo configuration device.

    :param channel: RTIO channel number
    :param pgia_device: Name of the Sampler PGIA gain setting SPI bus
    :param cpld0_device: Name of the first Urukul CPLD SPI bus
    :param cpld1_device: Name of the second Urukul CPLD SPI bus
    :param dds0_device: Name of the AD9910 device for the DDS on the first
        Urukul
    :param dds1_device: Name of the AD9910 device for the DDS on the second
        Urukul
    :param gains: Initial value for PGIA gains shift register
        (default: 0x0000). Knowledge of this state is not transferred
        between experiments.
    :param core_device: Core device name
    """
    kernel_invariants = {"channel", "core", "pgia", "cpld0", "cpld1",
                         "dds0", "dds1", "ref_period_mu"}

    def __init__(self, dmgr, channel, pgia_device,
                 cpld0_device, cpld1_device,
                 dds0_device, dds1_device,
                 gains=0x0000, core_device="core"):

        self.core = dmgr.get(core_device)
        self.pgia = dmgr.get(pgia_device)
        self.pgia.update_xfer_duration_mu(div=4, length=16)
        self.dds0 = dmgr.get(dds0_device)
        self.dds1 = dmgr.get(dds1_device)
        self.cpld0 = dmgr.get(cpld0_device)
        self.cpld1 = dmgr.get(cpld1_device)
        self.channel = channel
        self.gains = gains
        self.ref_period_mu = self.core.seconds_to_mu(
                self.core.coarse_ref_period)
        assert self.ref_period_mu == self.core.ref_multiplier

    @kernel
    def init(self):
        """Initialize the Servo, Sampler and both Urukuls.

        Leaves the Servo disabled (see :meth:`set_config`), resets all DDS.

        Urukul initialization is performed blindly as there is no readback from
        the DDS or the CPLDs.

        This method does not alter the profile configuration memory
        or the channel controls.
        """
        self.set_config(enable=0)
        delay(3*us)  # pipeline flush

        self.pgia.set_config_mu(
            sampler.SPI_CONFIG | spi.SPI_END,
            16, 4, sampler.SPI_CS_PGIA)

        self.cpld0.init(blind=True)
        cfg0 = self.cpld0.cfg_reg
        self.cpld0.cfg_write(cfg0 | (0xf << urukul.CFG_MASK_NU))
        self.dds0.init(blind=True)
        self.cpld0.cfg_write(cfg0)

        self.cpld1.init(blind=True)
        cfg1 = self.cpld1.cfg_reg
        self.cpld1.cfg_write(cfg1 | (0xf << urukul.CFG_MASK_NU))
        self.dds1.init(blind=True)
        self.cpld1.cfg_write(cfg1)

    @kernel
    def write(self, addr, value):
        """Write to Servo memory.

        This method advances the timeline by one coarse RTIO cycle.

        :param addr: Memory location address.
        :param value: Data to be written.
        """
        rtio_output(now_mu(), self.channel, addr | WE, value)
        delay_mu(self.ref_period_mu)

    @kernel
    def read(self, addr):
        """Read from Servo memory.

        This method does not advance the timeline but consumes all slack.

        :param addr: Memory location address.
        """
        rtio_output(now_mu(), self.channel, addr, 0)
        return rtio_input_data(self.channel)

    @kernel
    def set_config(self, enable):
        """Set SU Servo configuration.

        Disabling takes up to 2 Servo cycles (~2.2 µs) to clear
        the processing pipeline.

        This method advances the timeline by one Servo memory access.

        :param enable: Enable Servo operation.
        """
        self.write(CONFIG_ADDR, enable)

    @kernel
    def get_status(self):
        """Get current SU Servo status.

        This method does not advance the timeline but consumes all slack.
        This method returns and clears the clip indicator for all channels.

        :return: Status. Bit 0: enabled, bit 1: done,
          bits 8-15: channel clip indicators.
        """
        return self.read(CONFIG_ADDR)

    @kernel
    def get_adc_mu(self, adc):
        """Get an ADC reading (IIR filter input X0) in machine units.

        This method does not advance the timeline but consumes all slack.

        :param adc: ADC channel number (0-7)
        :return: 17 bit signed X0
        """
        # State memory entries are 25 bits. Due to the pre-adder dynamic
        # range, X0/X1/OFFSET are only 24 bits. Finally, the RTIO interface
        # only returns the 18 MSBs (the width of the coefficient memory).
        return self.read(STATE_SEL | (adc << 1) | (1 << 8))

    @kernel
    def set_pgia_mu(self, channel, gain):
        """Set instrumentation amplifier gain of a ADC channel.

        The four gain settings (0, 1, 2, 3) corresponds to gains of
        (1, 10, 100, 1000) respectively.

        :param channel: Channel index
        :param gain: Gain setting
        """
        gains = self.gains
        gains &= ~(0b11 << (channel*2))
        gains |= gain << (channel*2)
        self.pgia.write(gains << 16)
        self.gains = gains

    @kernel
    def get_adc(self, channel):
        """Get an ADC reading (IIR filter input X0).

        This method does not advance the timeline but consumes all slack.

        :param adc: ADC channel number (0-7)
        :return: ADC voltage
        """
        val = (self.get_adc_mu(channel) >> 1) & 0xffff
        mask = 1 << 15
        val = -(val & mask) + (val & ~mask)
        gain = (self.gains >> (channel*2)) & 0b11
        return sampler.adc_mu_to_volt(val, gain)


class Channel:
    """Sampler-Urukul Servo channel

    :param channel: RTIO channel number
    :param servo_device: Name of the parent SUServo device
    """
    kernel_invariants = {"channel", "core", "servo", "servo_channel"}

    def __init__(self, dmgr, channel, servo_device):
        self.servo = dmgr.get(servo_device)
        self.core = self.servo.core
        self.channel = channel
        # FIXME: this assumes the mem channel is right after the control
        # channels
        self.servo_channel = self.channel + 8 - self.servo.channel

    @kernel
    def set(self, en_out, en_iir=0, profile=0):
        """Operate channel.

        This method does not advance the timeline.
        Output RF switch setting takes effect immediately.
        IIR updates take place once the RF switch has been enabled for the
        configured delay and the profile setting has been stable.

        :param en_out: RF switch enable
        :param en_iir: IIR updates enable
        :param profile: Active profile (0-31)
        """
        rtio_output(now_mu(), self.channel, 0,
                    en_out | (en_iir << 1) | (profile << 2))

    @kernel
    def set_dds_mu(self, profile, ftw, offs, pow_=0):
        """Set profile DDS coefficients in machine units.

        .. seealso:: :meth:`set_amplitude`

        :param profile: Profile number (0-31)
        :param ftw: Frequency tuning word (32 bit unsigned)
        :param offs: IIR offset (17 bit signed)
        :param pow_: Phase offset word (16 bit)
        """
        base = (self.servo_channel << 8) | (profile << 3)
        self.servo.write(base + 0, ftw >> 16)
        self.servo.write(base + 6, ftw)
        self.servo.write(base + 4, offs)
        self.servo.write(base + 2, pow_)

    @kernel
    def set_dds(self, profile, frequency, offset, phase=0.):
        """Set profile DDS coefficients.

        This method advances the timeline by four Servo memory accesses.
        Profile parameter changes are not synchronized. Activate a different
        profile or stop the servo to ensure synchronous changes.

        :param profile: Profile number (0-31)
        :param frequency: DDS frequency in Hz
        :param offset: IIR offset (negative setpoint) in units of full scale.
            For positive ADC voltages as setpoints, this should be negative.
        :param phase: DDS phase in turns
        """
        if self.servo_channel < 4:
            dds = self.servo.dds0
        else:
            dds = self.servo.dds1
        ftw = dds.frequency_to_ftw(frequency)
        pow_ = dds.turns_to_pow(phase)
        offs = int(round(offset*(1 << COEFF_WIDTH - 1)))
        self.set_dds_mu(profile, ftw, offs, pow_)

    @kernel
    def set_iir_mu(self, profile, adc, a1, b0, b1, dly=0):
        """Set profile IIR coefficients in machine units.

        The recurrence relation is (all data signed and MSB aligned):

        .. math::
            a_0 y_n = a_1 y_{n - 1} + b_0 (x_n + o)/2 + b_1 (x_{n - 1} + o)/2

        Where:

            * :math:`y_n` and :math:`y_{n-1}` are the current and previous
              filter outputs, clipped to :math:`[0, 1]`.
            * :math:`x_n` and :math:`x_{n-1}` are the current and previous
              filter inputs
            * :math:`o` is the offset
            * :math:`a_0` is the normalization factor :math:`2^{11}`
            * :math:`a_1` is the feedback gain
            * :math:`b_0` and :math:`b_1` are the feedforward gains for the two
              delays

        .. seealso:: :meth:`set_iir`

        :param profile: Profile number (0-31)
        :param adc: ADC channel to take IIR input from (0-7)
        :param a1: 18 bit signed A1 coefficient (Y1 coefficient,
            feedback, integrator gain)
        :param b0: 18 bit signed B0 coefficient (recent,
            X0 coefficient, feed forward, proportional gain)
        :param b1: 18 bit signed B1 coefficient (old,
            X1 coefficient, feed forward, proportional gain)
        :param dly: IIR update suppression time. In units of IIR cycles
            (~1.2 µs, 0-255)
        """
        base = (self.servo_channel << 8) | (profile << 3)
        self.servo.write(base + 3, adc | (dly << 8))
        self.servo.write(base + 1, b1)
        self.servo.write(base + 5, a1)
        self.servo.write(base + 7, b0)

    @kernel
    def set_iir(self, profile, adc, gain, corner=0., limit=0., delay=0.):
        """Set profile IIR coefficients.

        This method advances the timeline by four Servo memory accesses.
        Profile parameter changes are not synchronized. Activate a different
        profile or stop the servo to ensure synchronous changes.

        Gains are given in units of output full per scale per input full scale.

        The transfer function is (up to time discretization and
        coefficient quantization errors):

        .. math::
            H(s) = K \\frac{1 + \\frac{s}{\\omega_0}}
                {\\frac{1}{g} + \\frac{s}{\\omega_0}}

        Where:
            * :math:`s = \\sigma + i\\omega` is the complex frequency
            * :math:`K` is the proportional gain
            * :math:`\\omega_0 = 2\\pi f_0` is the integrator corner frequency
            * :math:`g` is the integrator gain limit

        :param profile: Profile number (0-31)
        :param adc: ADC channel to take IIR input from (0-7)
        :param gain: Proportional gain (1). This is usually negative (closed
            loop, positive ADC voltage, positive setpoint). When 0, this
            implements a pure I controller with unit gain frequency at
            `corner` (use the sign of `corner` for overall gain sign).
        :param corner: Integrator corner frequency (Hz). When 0 (the default)
            this implements a pure P controller.
        :param limit: Integrator gain limit (1). When 0 (the default) the
            integrator gain limit is infinite. Positive.
        :param delay: Delay (in seconds, 0-300 µs) before allowing IIR updates
            after invoking :meth:`set`.
        """
        B_NORM = 1 << COEFF_SHIFT + 1
        A_NORM = 1 << COEFF_SHIFT
        PI_TS = 3.1415927*T_CYCLE
        COEFF_MAX = 1 << COEFF_WIDTH - 1

        gain *= B_NORM
        corner *= PI_TS

        if corner == 0.:
            # pure P
            a1_ = 0
            b1_ = 0
            b0_ = int(round(gain))
        else:
            a1_ = A_NORM
            if gain == 0.:
                # pure I
                b0 = (2*B_NORM)*corner
                b1_ = 0
            else:
                # PI
                k = gain*corner
                b1 = k - gain
                b0 = k + gain
                if limit != 0.:
                    # PI with limit
                    q = corner/limit
                    qr = 1./(1. + q)
                    a1_ = int(round(a1_*(1. - q)*qr))
                    b0 *= qr
                    b1 *= qr
                b1_ = int(round(b1))
            b0_ = int(round(b0))

            if b1_ == -b0_:
                raise ValueError("low corner, gain, limit")

        if (b0_ >= COEFF_MAX or b0_ < -COEFF_MAX or
                b1_ >= COEFF_MAX or b1_ < -COEFF_MAX):
            raise ValueError("high corner, gain, limit")

        dly = int(round(delay/T_CYCLE))
        self.set_iir_mu(profile, adc, a1_, b0_, b1_, dly)

    @kernel
    def get_profile_mu(self, profile, data):
        """Retrieve profile data.

        The data is returned in the `data` argument as:
        `[ftw >> 16, b1, pow, adc | (delay << 8), offset, a1, ftw, b0]`.

        This method advances the timeline by 32 µs and consumes all slack.
        Profile data is returned 

        :param profile: Profile number (0-31)
        :param data: List of 8 integers to write the profile data into
        """
        base = (self.servo_channel << 8) | (profile << 3)
        for i in range(len(data)):
            data[i] = self.servo.read(base + i)
            delay(4*us)

    @kernel
    def get_y_mu(self, profile):
        """Get a profile's IIR state (filter output, Y0) in machine units.

        The IIR state is also know as the "integrator", or the DDS amplitude
        scale factor. It is 18 bits wide and unsigned.

        This method does not advance the timeline but consumes all slack.

        :param profile: Profile number (0-31)
        :return: 18 bit unsigned Y0
        """
        return self.servo.read(STATE_SEL | (self.servo_channel << 5) | profile)

    @kernel
    def get_y(self, profile):
        """Get a profile's IIR state (filter output, Y0).

        The IIR state is also know as the "integrator", or the DDS amplitude
        scale factor. It is 18 bits wide and unsigned.

        This method does not advance the timeline but consumes all slack.

        :param profile: Profile number (0-31)
        :return: IIR filter output in Y0 units of full scale
        """
        return self.get_y_mu(profile)*(1./(1 << COEFF_WIDTH - 1))

    @kernel
    def set_y_mu(self, profile, y):
        """Set a profile's IIR state (filter output, Y0) in machine units.

        The IIR state is also know as the "integrator", or the DDS amplitude
        scale factor. It is 18 bits wide and unsigned.

        This method must not be used when the Servo
        could be writing to the same location. Either deactivate the profile,
        or deactivate IIR updates, or disable Servo iterations.

        This method advances the timeline by one Servo memory access.

        :param profile: Profile number (0-31)
        :param y: 17 bit unsigned Y0
        """
        # State memory is 25 bits wide and signed.
        # Reads interact with the 18 MSBs (coefficient memory width)
        self.servo.write(STATE_SEL | (self.servo_channel << 5) | profile, y)

    @kernel
    def set_y(self, profile, y):
        """Set a profile's IIR state (filter output, Y0).

        The IIR state is also know as the "integrator", or the DDS amplitude
        scale factor. It is 18 bits wide and unsigned.

        This method must not be used when the Servo
        could be writing to the same location. Either deactivate the profile,
        or deactivate IIR updates, or disable Servo iterations.

        This method advances the timeline by one Servo memory access.

        :param profile: Profile number (0-31)
        :param y: IIR state in units of full scale
        """
        self.set_y_mu(profile, int(round((1 << COEFF_WIDTH - 1)*y)))
