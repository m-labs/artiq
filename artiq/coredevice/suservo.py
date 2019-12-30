from artiq.language.core import kernel, delay, delay_mu, portable
from artiq.language.units import us, ns
from artiq.coredevice.rtio import rtio_output, rtio_input_data
from artiq.coredevice import spi2 as spi
from artiq.coredevice import urukul, sampler


COEFF_WIDTH = 18
Y_FULL_SCALE_MU = (1 << (COEFF_WIDTH - 1)) - 1
COEFF_DEPTH = 10 + 1
WE = 1 << COEFF_DEPTH + 1
STATE_SEL = 1 << COEFF_DEPTH
CONFIG_SEL = 1 << COEFF_DEPTH - 1
CONFIG_ADDR = CONFIG_SEL | STATE_SEL
T_CYCLE = (2*(8 + 64) + 2)*8*ns  # Must match gateware Servo.t_cycle.
COEFF_SHIFT = 11


@portable
def y_mu_to_full_scale(y):
    """Convert servo Y data from machine units to units of full scale."""
    return y / Y_FULL_SCALE_MU


@portable
def adc_mu_to_volts(x, gain):
    """Convert servo ADC data from machine units to Volt."""
    val = (x >> 1) & 0xffff
    mask = 1 << 15
    val = -(val & mask) + (val & ~mask)
    return sampler.adc_mu_to_volt(val, gain)


class SUServo:
    """Sampler-Urukul Servo parent and configuration device.

    Sampler-Urukul Servo is a integrated device controlling one
    8-channel ADC (Sampler) and two 4-channel DDS (Urukuls) with a DSP engine
    connecting the ADC data and the DDS output amplitudes to enable
    feedback. SU Servo can for example be used to implement intensity
    stabilization of laser beams with an amplifier and AOM driven by Urukul
    and a photodetector connected to Sampler.

    Additionally SU Servo supports multiple preconfigured profiles per channel
    and features like automatic integrator hold.

    Notes:

        * See the SU Servo variant of the Kasli target for an example of how to
          connect the gateware and the devices. Sampler and each Urukul need
          two EEM connections.
        * Ensure that both Urukuls are AD9910 variants and have the on-board
          dip switches set to 1100 (first two on, last two off).
        * Refer to the Sampler and Urukul documentation and the SU Servo
          example device database for runtime configuration of the devices
          (PLLs, gains, clock routing etc.)

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
        """Initialize the servo, Sampler and both Urukuls.

        Leaves the servo disabled (see :meth:`set_config`), resets and
        configures all DDS.

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
        """Write to servo memory.

        This method advances the timeline by one coarse RTIO cycle.

        :param addr: Memory location address.
        :param value: Data to be written.
        """
        addr |= WE
        value &= (1 << COEFF_WIDTH) - 1
        value |= (addr >> 8) << COEFF_WIDTH
        addr = addr & 0xff
        rtio_output((self.channel << 8) | addr, value)
        delay_mu(self.ref_period_mu)

    @kernel
    def read(self, addr):
        """Read from servo memory.

        This method does not advance the timeline but consumes all slack.

        :param addr: Memory location address.
        """
        value = (addr >> 8) << COEFF_WIDTH
        addr = addr & 0xff
        rtio_output((self.channel << 8) | addr, value)
        return rtio_input_data(self.channel)

    @kernel
    def set_config(self, enable):
        """Set SU Servo configuration.

        This method advances the timeline by one servo memory access.
        It does not support RTIO event replacement.

        :param enable (int): Enable servo operation. Enabling starts servo
            iterations beginning with the ADC sampling stage. The first DDS
            update will happen about two servo cycles (~2.3 µs) after enabling
            the servo. The delay is deterministic.
            This also provides a mean for synchronization of servo updates to
            other RTIO activity.
            Disabling takes up to two servo cycles (~2.3 µs) to clear the
            processing pipeline.
        """
        self.write(CONFIG_ADDR, enable)

    @kernel
    def get_status(self):
        """Get current SU Servo status.

        This method does not advance the timeline but consumes all slack.

        The ``done`` bit indicates that a SU Servo cycle has completed.
        It is pulsed for one RTIO cycle every SU Servo cycle and asserted
        continuously when the servo is not ``enabled`` and the pipeline has
        drained (the last DDS update is done).

        This method returns and clears the clip indicator for all channels.
        An asserted clip indicator corresponds to the servo having encountered
        an input signal on an active channel that would have resulted in the
        IIR state exceeding the output range.

        :return: Status. Bit 0: enabled, bit 1: done,
          bits 8-15: channel clip indicators.
        """
        return self.read(CONFIG_ADDR)

    @kernel
    def get_adc_mu(self, adc):
        """Get the latest ADC reading (IIR filter input X0) in machine units.

        This method does not advance the timeline but consumes all slack.

        If reading servo state through this method collides with the servo
        writing that same data, the data can become invalid. To ensure
        consistent and valid data, stop the servo before using this method.

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
        """Get the latest ADC reading (IIR filter input X0).

        This method does not advance the timeline but consumes all slack.

        If reading servo state through this method collides with the servo
        writing that same data, the data can become invalid. To ensure
        consistent and valid data, stop the servo before using this method.

        The PGIA gain setting must be known prior to using this method, either
        by setting the gain (:meth:`set_pgia_mu`) or by supplying it
        (:attr:`gains` or via the constructor/device database).

        :param adc: ADC channel number (0-7)
        :return: ADC voltage
        """
        val = self.get_adc_mu(channel)
        gain = (self.gains >> (channel*2)) & 0b11
        return adc_mu_to_volts(val, gain)


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

        This method does not advance the timeline. Output RF switch setting
        takes effect immediately and is independent of any other activity
        (profile settings, other channels). The RF switch behaves like
        :class:`artiq.coredevice.ttl.TTLOut`. RTIO event replacement is
        supported. IIR updates take place once the RF switch has been enabled
        for the configured delay and the profile setting has been stable.
        Profile changes take between one and two servo cycles to reach the DDS.

        :param en_out: RF switch enable
        :param en_iir: IIR updates enable
        :param profile: Active profile (0-31)
        """
        rtio_output(self.channel << 8,
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
        self.servo.write(base + 6, (ftw & 0xffff))
        self.set_dds_offset_mu(profile, offs)
        self.servo.write(base + 2, pow_)

    @kernel
    def set_dds(self, profile, frequency, offset, phase=0.):
        """Set profile DDS coefficients.

        This method advances the timeline by four servo memory accesses.
        Profile parameter changes are not synchronized. Activate a different
        profile or stop the servo to ensure synchronous changes.

        :param profile: Profile number (0-31)
        :param frequency: DDS frequency in Hz
        :param offset: IIR offset (negative setpoint) in units of full scale,
            see :meth:`dds_offset_to_mu`
        :param phase: DDS phase in turns
        """
        if self.servo_channel < 4:
            dds = self.servo.dds0
        else:
            dds = self.servo.dds1
        ftw = dds.frequency_to_ftw(frequency)
        pow_ = dds.turns_to_pow(phase)
        offs = self.dds_offset_to_mu(offset)
        self.set_dds_mu(profile, ftw, offs, pow_)

    @kernel
    def set_dds_offset_mu(self, profile, offs):
        """Set only IIR offset in DDS coefficient profile.

        See :meth:`set_dds_mu` for setting the complete DDS profile.

        :param profile: Profile number (0-31)
        :param offs: IIR offset (17 bit signed)
        """
        base = (self.servo_channel << 8) | (profile << 3)
        self.servo.write(base + 4, offs)

    @kernel
    def set_dds_offset(self, profile, offset):
        """Set only IIR offset in DDS coefficient profile.

        See :meth:`set_dds` for setting the complete DDS profile.

        :param profile: Profile number (0-31)
        :param offset: IIR offset (negative setpoint) in units of full scale
        """
        self.set_dds_offset_mu(profile, self.dds_offset_to_mu(offset))

    @portable
    def dds_offset_to_mu(self, offset):
        """Convert IIR offset (negative setpoint) from units of full scale to
        machine units (see :meth:`set_dds_mu`, :meth:`set_dds_offset_mu`).

        For positive ADC voltages as setpoints, this should be negative. Due to
        rounding and representation as two's complement, ``offset=1`` can not
        be represented while ``offset=-1`` can.
        """
        return int(round(offset * (1 << COEFF_WIDTH - 1)))

    @kernel
    def set_iir_mu(self, profile, adc, a1, b0, b1, dly=0):
        """Set profile IIR coefficients in machine units.

        The recurrence relation is (all data signed and MSB aligned):

        .. math::
            a_0 y_n = a_1 y_{n - 1} + b_0 (x_n + o)/2 + b_1 (x_{n - 1} + o)/2

        Where:

            * :math:`y_n` and :math:`y_{n-1}` are the current and previous
              filter outputs, clipped to :math:`[0, 1[`.
            * :math:`x_n` and :math:`x_{n-1}` are the current and previous
              filter inputs in :math:`[-1, 1[`.
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
            (~1.2 µs, 0-255).
        """
        base = (self.servo_channel << 8) | (profile << 3)
        self.servo.write(base + 3, adc | (dly << 8))
        self.servo.write(base + 1, b1)
        self.servo.write(base + 5, a1)
        self.servo.write(base + 7, b0)

    @kernel
    def set_iir(self, profile, adc, kp, ki=0., g=0., delay=0.):
        """Set profile IIR coefficients.

        This method advances the timeline by four servo memory accesses.
        Profile parameter changes are not synchronized. Activate a different
        profile or stop the servo to ensure synchronous changes.

        Gains are given in units of output full per scale per input full scale.

        The transfer function is (up to time discretization and
        coefficient quantization errors):

        .. math::
            H(s) = k_p + \\frac{k_i}{s + \\frac{k_i}{g}}

        Where:
            * :math:`s = \\sigma + i\\omega` is the complex frequency
            * :math:`k_p` is the proportional gain
            * :math:`k_i` is the integrator gain
            * :math:`g` is the integrator gain limit

        :param profile: Profile number (0-31)
        :param adc: ADC channel to take IIR input from (0-7)
        :param kp: Proportional gain (1). This is usually negative (closed
            loop, positive ADC voltage, positive setpoint). When 0, this
            implements a pure I controller.
        :param ki: Integrator gain (rad/s). When 0 (the default)
            this implements a pure P controller. Same sign as ``kp``.
        :param g: Integrator gain limit (1). When 0 (the default) the
            integrator gain limit is infinite. Same sign as ``ki``.
        :param delay: Delay (in seconds, 0-300 µs) before allowing IIR updates
            after invoking :meth:`set`. This is rounded to the nearest number
            of servo cycles (~1.2 µs). Since the RF switch (:meth:`set`) can be
            opened at any time relative to the servo cycle, the first DDS
            update that carries updated IIR data will occur approximately
            between ``delay + 1 cycle`` and ``delay + 2 cycles`` after
            :meth:`set`.
        """
        B_NORM = 1 << COEFF_SHIFT + 1
        A_NORM = 1 << COEFF_SHIFT
        COEFF_MAX = 1 << COEFF_WIDTH - 1

        kp *= B_NORM
        if ki == 0.:
            # pure P
            a1 = 0
            b1 = 0
            b0 = int(round(kp))
        else:
            # I or PI
            ki *= B_NORM*T_CYCLE/2.
            if g == 0.:
                c = 1.
                a1 = A_NORM
            else:
                c = 1./(1. + ki/(g*B_NORM))
                a1 = int(round((2.*c - 1.)*A_NORM))
            b0 = int(round(kp + ki*c))
            b1 = int(round(kp + (ki - 2.*kp)*c))
            if b1 == -b0:
                raise ValueError("low integrator gain and/or gain limit")

        if (b0 >= COEFF_MAX or b0 < -COEFF_MAX or
                b1 >= COEFF_MAX or b1 < -COEFF_MAX):
            raise ValueError("high gains")

        dly = int(round(delay/T_CYCLE))
        self.set_iir_mu(profile, adc, a1, b0, b1, dly)

    @kernel
    def get_profile_mu(self, profile, data):
        """Retrieve profile data.

        Profile data is returned in the ``data`` argument in machine units
        packed as: ``[ftw >> 16, b1, pow, adc | (delay << 8), offset, a1,
        ftw & 0xffff, b0]``.

        .. seealso:: The individual fields are described in
            :meth:`set_iir_mu` and :meth:`set_dds_mu`.

        This method advances the timeline by 32 µs and consumes all slack.

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
        scale factor. It is 17 bits wide and unsigned.

        This method does not advance the timeline but consumes all slack.

        If reading servo state through this method collides with the servo
        writing that same data, the data can become invalid. To ensure
        consistent and valid data, stop the servo before using this method.

        :param profile: Profile number (0-31)
        :return: 17 bit unsigned Y0
        """
        return self.servo.read(STATE_SEL | (self.servo_channel << 5) | profile)

    @kernel
    def get_y(self, profile):
        """Get a profile's IIR state (filter output, Y0).

        The IIR state is also know as the "integrator", or the DDS amplitude
        scale factor. It is 17 bits wide and unsigned.

        This method does not advance the timeline but consumes all slack.

        If reading servo state through this method collides with the servo
        writing that same data, the data can become invalid. To ensure
        consistent and valid data, stop the servo before using this method.

        :param profile: Profile number (0-31)
        :return: IIR filter output in Y0 units of full scale
        """
        return y_mu_to_full_scale(self.get_y_mu(profile))

    @kernel
    def set_y_mu(self, profile, y):
        """Set a profile's IIR state (filter output, Y0) in machine units.

        The IIR state is also know as the "integrator", or the DDS amplitude
        scale factor. It is 17 bits wide and unsigned.

        This method must not be used when the servo could be writing to the
        same location. Either deactivate the profile, or deactivate IIR
        updates, or disable servo iterations.

        This method advances the timeline by one servo memory access.

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
        scale factor. It is 17 bits wide and unsigned.

        This method must not be used when the servo could be writing to the
        same location. Either deactivate the profile, or deactivate IIR
        updates, or disable servo iterations.

        This method advances the timeline by one servo memory access.

        :param profile: Profile number (0-31)
        :param y: IIR state in units of full scale
        """
        y_mu = int(round(y * Y_FULL_SCALE_MU))
        self.set_y_mu(profile, y_mu)
        return y_mu
