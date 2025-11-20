from math import ceil, log2

from artiq.language.core import kernel, delay, delay_mu, portable
from artiq.language.types import TFloat, TInt32, TTuple
from artiq.language.units import us, ns
from artiq.coredevice.rtio import rtio_output, rtio_input_data
from artiq.coredevice import spi2 as spi
from artiq.coredevice import ad9910, urukul, sampler


COEFF_WIDTH = 18
Y_FULL_SCALE_MU = (1 << (COEFF_WIDTH - 1)) - 1
T_CYCLE = (2*(8 + 64) + 2)*8*ns  # Must match gateware Servo.t_cycle.
COEFF_SHIFT = 11
PROFILE_WIDTH = 5


@portable
def y_mu_to_full_scale(y):
    """Convert servo Y data from machine units to units of full scale."""
    return y / Y_FULL_SCALE_MU


@portable
def adc_mu_to_volts(x, gain, corrected_fs=True):
    """Convert servo ADC data from machine units to volts."""
    val = (x >> 1) & 0xffff
    mask = 1 << 15
    val = -(val & mask) + (val & ~mask)
    return sampler.adc_mu_to_volt(val, gain, corrected_fs)


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
    :param cpld_devices: Names of the Urukul CPLD SPI buses
    :param dds_devices: Names of the AD9910 devices
    :param gains: Initial value for PGIA gains shift register
        (default: 0x0000). Knowledge of this state is not transferred
        between experiments.
    :param sampler_hw_rev: Sampler's revision string
    :param core_device: Core device name
    """
    kernel_invariants = {"channel", "core", "pgia", "cplds", "ddses",
                         "ref_period_mu", "corrected_fs", "io_dly_width",
                         "we", "state_sel", "num_channels", "config_addr"}

    def __init__(self, dmgr, channel, pgia_device,
                 cpld_devices, dds_devices,
                 gains=0x0000, sampler_hw_rev="v2.2", core_device="core"):

        self.core = dmgr.get(core_device)
        self.pgia = dmgr.get(pgia_device)
        self.pgia.update_xfer_duration_mu(div=4, length=16)
        assert len(dds_devices) == len(cpld_devices)
        self.ddses = [dmgr.get(dds) for dds in dds_devices]
        self.cplds = [dmgr.get(cpld) for cpld in cpld_devices]
        self.channel = channel
        self.gains = gains
        self.ref_period_mu = self.core.seconds_to_mu(
            self.core.coarse_ref_period)
        self.corrected_fs = sampler.Sampler.use_corrected_fs(sampler_hw_rev)
        assert self.ref_period_mu == self.core.ref_multiplier

        io_dly_width = log2(self.core.ref_multiplier)
        assert io_dly_width.is_integer()
        self.io_dly_width = int(io_dly_width)

        self.num_channels = 4 * len(dds_devices)
        channel_adr_width = ceil(log2(self.num_channels))
        # (1 << 2) memory addresses for each channel profile
        # Each memory slot addresses (1 << 1) coefficients through granularity
        coeff_adr_width = PROFILE_WIDTH + channel_adr_width + 3
        coeff_depth = 10 + (len(cpld_devices) - 1).bit_length()
        self.we = 1 << coeff_depth + 2
        self.phase_sel = 1 << coeff_depth + 1
        self.state_sel = 1 << coeff_depth
        self.word_sel = 1 << coeff_depth
        config_sel = 1 << coeff_depth - 1
        self.config_addr = self.state_sel | config_sel

    @staticmethod
    def get_rtio_channels(channel, **kwargs):
        return [(channel, None)]

    @kernel
    def init(self):
        """Initialize the servo, Sampler and both Urukuls.

        Leaves the servo disabled (see :meth:`set_config`), resets and
        configures all DDS.

        On protocol revision 8 Urukuls, initialization is performed blindly
        as there is no readback from the DDS or the CPLDs. Presence detection
        via readback is performed on protocol revision 9 Urukuls.

        This method does not alter the profile configuration memory
        or the channel controls.
        """
        self.set_config(enable=0)
        delay(3*us)  # pipeline flush

        self.pgia.set_config_mu(
            sampler.SPI_CONFIG | spi.SPI_END,
            16, 4, sampler.SPI_CS_PGIA)

        io_update_delays = [ 0 for _ in self.cplds ]
        for i in range(len(self.cplds)):
            cpld = self.cplds[i]
            dds = self.ddses[i]

            use_miso = cpld.proto_rev == urukul.STA_PROTO_REV_9

            cpld.init(blind=not use_miso)
            prev_cpld_cfg = int64(cpld.cfg_reg)
            dds.init(blind=not use_miso)
            cpld.cfg_write(prev_cpld_cfg)
            io_update_delays[i] = dds.sync_data.io_update_delay

        self.set_config(enable=0, write_delay=True, io_update_delays=io_update_delays)

    @kernel
    def write(self, addr, value):
        """Write to servo memory.

        This method advances the timeline by one coarse RTIO cycle.

        :param addr: Memory location address.
        :param value: Data to be written.
        """
        addr |= self.we
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
    def set_config(self, enable, write_delay=False, io_update_delays=[0]):
        """Set SU Servo configuration.

        This method advances the timeline by one servo memory access.
        It does not support RTIO event replacement.

        :param int enable: Enable servo operation. Enabling starts servo
            iterations beginning with the ADC sampling stage. The first DDS
            update will happen about two servo cycles (~2.3 µs) after enabling
            the servo. The delay is deterministic.
            This also provides a mean for synchronization of servo updates to
            other RTIO activity.
            Disabling takes up to two servo cycles (~2.3 µs) to clear the
            processing pipeline.
        
        :param bool write_delay: Write enable for IO_UPDATE delays.

        :param list io_update_delays: List of IO_UPDATE delays for each
            Urukul. Requires enabling synchronization to configure.
        """
        value = enable
        if write_delay:
            value |= (1 << 1)
            for i in range(len(io_update_delays)):
                value |= (io_update_delays[i] << (i * self.io_dly_width + 2))
        self.write(self.config_addr, value)

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
        return self.read(self.config_addr)

    @kernel
    def get_adc_mu(self, adc):
        """Get the latest ADC reading (IIR filter input X0) in machine units.

        This method does not advance the timeline but consumes all slack.

        If reading servo state through this method collides with the servo
        writing that same data, the data can become invalid. To ensure
        consistent and valid data, stop the servo before using this method.

        :param adc: ADC channel number (0-7)
        :return: 17-bit signed X0
        """
        # State memory entries are 25 bits. Due to the pre-adder dynamic
        # range, X0/X1/OFFSET are only 24 bits. Finally, the RTIO interface
        # only returns the 18 MSBs (the width of the coefficient memory).
        return self.read(self.state_sel
                         | ((adc << 1) + (self.num_channels << PROFILE_WIDTH)))

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
        return adc_mu_to_volts(val, gain, self.corrected_fs)

    @kernel
    def clear_dds_phase_accumulator(self):
        """Clear all DDS phase accumulators.

        This method clears the phase accumulator by enabling autoclear, and
        setting the FTW of all the DDS single-tone profiles to 0.

        SU-Servo is assumed to be disabled with its pipeline drained before
        invoking this method.
        """
        self.core.break_realtime()
        num_of_urukuls = len(self.cplds)
        for i in range(num_of_urukuls):
            cpld = self.cplds[i]
            dds = self.ddses[i]._inner_dds
            cpld.cfg_mask_nu_all(0xf)
            dds.set_cfr1(phase_autoclear=1)
            dds.write64(ad9910._AD9910_REG_PROFILE0 + urukul.DEFAULT_PROFILE, 0, 0)
            cpld.cfg_io_update_all(0xf)
            cpld.cfg_io_update_all(0)
            dds.set_cfr1(phase_autoclear=0)
            cpld.cfg_io_update_all(0xf)
            cpld.cfg_io_update_all(0)
            cpld.cfg_mask_nu_all(0)


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
        # This assumes the mem channel is right after the control channels
        # Make sure this is always the case in eem.py
        self.servo_channel = (self.channel + self.servo.num_channels -
                              self.servo.channel)
        self.dds = self.servo.ddses[self.servo_channel // 4]

    @staticmethod
    def get_rtio_channels(channel, **kwargs):
        return [(channel, None)]

    @kernel
    def set(self, en_out, en_iir=0, en_pt=0, profile=0):
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
        :param en_pt: Phase tracking enable
        :param profile: Active profile (0-31)
        """
        rtio_output(self.channel << 8,
                    en_out | (en_iir << 1) | (en_pt << 2) | (profile << 3))

    @kernel
    def set_reference_time(self, profile, fiducial_mu):
        """Set reference time for "coherent phase mode" (see
        :meth:`~artiq.coredevice.ad9910.AD9910.set`).

        Fiducial time stamp refers to the variable `T` in phase tracking mode
        equation. See :meth:`artiq.coredevice.ad9910.AD9910.set_phase_mode`.
        Fiducial time stamp is defined as 0 immediately after the servo has
        been enabled.

        With en_pt=1 (see :meth:`set`), the DDS output phase of this channel
        will refer to this fiducial time stamp.

        This method advances the timeline by two coarse RTIO cycles.

        :param profile: Profile number (0-31)
        :param fiducial_mu: Fiducial time stamp in machine unit
        """
        addr = self.servo.phase_sel | (((self.servo_channel << PROFILE_WIDTH) | profile) << 1)
        self.servo.write(addr, fiducial_mu & 0xffff)
        self.servo.write(addr + 1, fiducial_mu >> 16)

    @kernel
    def copy_reference_time(self, profile):
        """Copy the reference time of the specified profile from the internal
        time stamp accumulator in real time.

        Fiducial time stamp refers to the variable `T` in phase tracking mode
        equation. See :meth:`artiq.coredevice.ad9910.AD9910.set_phase_mode`.
        Fiducial time stamp is defined as 0 immediately after the servo has
        been enabled.

        With en_pt=1 (see :meth:`set`), the DDS output phase of this channel
        will refer to this copied fiducial time stamp.

        The coarse part of the time stamp is sourced from the internal time
        stamp accumulator of the servo. The accumulator only updates every
        coarse RTIO cycle. The fine part of the time stamp is provided by the
        corresponding part of the timeline cursor.

        This method advances the timeline by one coarse RTIO cycle.

        :param profile: Profile number (0-31)
        """
        addr = self.servo.phase_sel | self.servo.word_sel | (((self.servo_channel << PROFILE_WIDTH) | profile) << 1)
        self.servo.write(addr, 0)

    @kernel
    def get_reference_time(self, profile):
        """Reads the fiducial time stamp of the profile.
        See :meth:`set_reference_time` regarding the role of fiducial time
        stamp on phase tracking.

        :param profile: Profile number (0-31)
        :return: The fiducial time stamp of the profile
        """
        addr = self.servo.phase_sel | (((self.servo_channel << PROFILE_WIDTH) | profile) << 1)
        self.core.break_realtime()
        lo = self.servo.read(addr)
        self.core.break_realtime()
        hi = self.servo.read(addr + 1)
        return (hi << 16) | (lo & 0xffff)

    @kernel
    def clear_tracked_phase_accumulator(self):
        """Clears the tracked phase accumulator of this channel.
        The tracked phase accumulator is an internal register that tracks the
        corresponding register of the corresponding DDS. To properly track the
        accumulator of the DDS, both accumulators should be cleared before
        enabling the servo.

        This method advances the timeline by two coarse RTIO cycles.

        .. seealso:: The accumulator of the DDS can be cleared by 
            :meth:`~artiq.coredevice.suservo.SUServo.clear_dds_phase_accumulator`
        """
        addr = self.servo.phase_sel | (((1 << PROFILE_WIDTH) * self.servo.num_channels + (self.servo_channel << 1) | 1) << 1)
        self.servo.write(addr, 0)
        self.servo.write(addr + 1, 0)

    @kernel
    def get_tracked_phase_accumulator(self):
        """Reads the tracked phase accumulator of this channel.
        The tracked phase accumulator is an internal register that tracks the
        corresponding register of the corresponding DDS. Both registers are
        expected to update in real time.
        Since this is a two-part read, there might be word tearing. Either 
        disabling the servo, or setting the frequency tuning word (FTW) to 0,
        will avoid this word tearing issue.

        :return: The internally tracked phase accumulator
        """
        addr = self.servo.phase_sel | (((1 << PROFILE_WIDTH) * self.servo.num_channels + (self.servo_channel << 1) | 1) << 1)
        self.core.break_realtime()
        lo = self.servo.read(addr)
        self.core.break_realtime()
        hi = self.servo.read(addr + 1)
        return (hi << 16) | (lo & 0xffff)

    @kernel
    def clear_tracked_ftw(self):
        """Clears the tracked frequency tuning word (FTW) of this channel.
        The FTW on the DDS should be cleared before enabling the servo.

        This method advances the timeline by two coarse RTIO cycles.
        """
        addr = self.servo.phase_sel | (((1 << PROFILE_WIDTH) * self.servo.num_channels + (self.servo_channel << 1) | 0) << 1)
        self.servo.write(addr, 0)
        self.servo.write(addr + 1, 0)

    @kernel
    def get_tracked_ftw(self):
        """Reads the tracked frequency tuning word (FTW) of this channel.

        :return: The internally tracked FTW
        """
        addr = self.servo.phase_sel | (((1 << PROFILE_WIDTH) * self.servo.num_channels + (self.servo_channel << 1) | 0) << 1)
        self.core.break_realtime()
        lo = self.servo.read(addr)
        self.core.break_realtime()
        hi = self.servo.read(addr + 1)
        return (hi << 16) | (lo & 0xffff)

    @kernel
    def set_dds_mu(self, profile, ftw, offs, pow_=0):
        """Set profile DDS coefficients in machine units.

        See also :meth:`Channel.set_dds`.

        :param profile: Profile number (0-31)
        :param ftw: Frequency tuning word (32-bit unsigned)
        :param offs: IIR offset (17-bit signed)
        :param pow_: Phase offset word (16-bit)
        """
        base = ((self.servo_channel << PROFILE_WIDTH) | profile) << 3
        self.servo.write(base + 6, ftw >> 16)
        self.servo.write(base + 2, (ftw & 0xffff))
        self.set_dds_offset_mu(profile, offs)
        self.servo.write(base, pow_)

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
        ftw = self.dds.frequency_to_ftw(frequency)
        pow_ = self.dds.turns_to_pow(phase)
        offs = self.dds_offset_to_mu(offset)
        self.set_dds_mu(profile, ftw, offs, pow_)

    @kernel
    def set_dds_offset_mu(self, profile, offs):
        """Set only IIR offset in DDS coefficient profile.

        See :meth:`set_dds_mu` for setting the complete DDS profile.

        :param profile: Profile number (0-31)
        :param offs: IIR offset (17-bit signed)
        """
        base = ((self.servo_channel << PROFILE_WIDTH) | profile) << 3
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

        See also :meth:`Channel.set_iir`.

        :param profile: Profile number (0-31)
        :param adc: ADC channel to take IIR input from (0-7)
        :param a1: 18-bit signed A1 coefficient (Y1 coefficient,
            feedback, integrator gain)
        :param b0: 18-bit signed B0 coefficient (recent,
            X0 coefficient, feed forward, proportional gain)
        :param b1: 18-bit signed B1 coefficient (old,
            X1 coefficient, feed forward, proportional gain)
        :param dly: IIR update suppression time. In units of IIR cycles
            (~1.2 µs, 0-255).
        """
        base = ((self.servo_channel << PROFILE_WIDTH) | profile) << 3
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
        packed as: ``[pow, b1, ftw & 0xffff, adc | (delay << 8), offset, a1,
        ftw >> 16, b0]``.

        .. seealso:: The individual fields are described in
            :meth:`set_iir_mu` and :meth:`set_dds_mu`.

        This method advances the timeline by 32 µs and consumes all slack.

        :param profile: Profile number (0-31)
        :param data: List of 8 integers to write the profile data into
        """
        base = ((self.servo_channel << PROFILE_WIDTH) | profile) << 3
        for i in range(len(data)):
            data[i] = self.servo.read(base + i)
            delay(4*us)

    @kernel
    def get_y_mu(self, profile):
        """Get a profile's IIR state (filter output, Y0) in machine units.

        The IIR state is also known as the "integrator", or the DDS amplitude
        scale factor. It is 17 bits wide and unsigned.

        This method does not advance the timeline but consumes all slack.

        If reading servo state through this method collides with the servo
        writing that same data, the data can become invalid. To ensure
        consistent and valid data, stop the servo before using this method.

        :param profile: Profile number (0-31)
        :return: 17-bit unsigned Y0
        """
        return self.servo.read(self.servo.state_sel | (self.servo_channel << PROFILE_WIDTH) | profile)

    @kernel
    def get_y(self, profile):
        """Get a profile's IIR state (filter output, Y0).

        The IIR state is also known as the "integrator", or the DDS amplitude
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

        The IIR state is also known as the "integrator", or the DDS amplitude
        scale factor. It is 17 bits wide and unsigned.

        This method must not be used when the servo could be writing to the
        same location. Either deactivate the profile, or deactivate IIR
        updates, or disable servo iterations.

        This method advances the timeline by one servo memory access.

        :param profile: Profile number (0-31)
        :param y: 17-bit unsigned Y0
        """
        # State memory is 25 bits wide and signed.
        # Reads interact with the 18 MSBs (coefficient memory width)
        self.servo.write(self.servo.state_sel | (self.servo_channel << PROFILE_WIDTH) | profile, y)

    @kernel
    def set_y(self, profile, y):
        """Set a profile's IIR state (filter output, Y0).

        The IIR state is also known as the "integrator", or the DDS amplitude
        scale factor. It is 17 bits wide and unsigned.

        This method must not be used when the servo could be writing to the
        same location. Either deactivate the profile, or deactivate IIR
        updates, or disable servo iterations.

        This method advances the timeline by one servo memory access.

        :param profile: Profile number (0-31)
        :param y: IIR state in units of full scale
        """
        y_mu = int(round(y * Y_FULL_SCALE_MU))
        if y_mu < 0 or y_mu > (1 << 17) - 1:
            raise ValueError("Invalid SUServo y-value!")
        self.set_y_mu(profile, y_mu)
        return y_mu


class _MaskedIOUpdate:
    def __init__(self, core, cpld, dds, io_update):
        self.cpld = cpld
        self.dds = dds
        self.core = core
        self.io_update = io_update

        # Synchronized SU-Servo uses the designated I/O update pin.
        # When communicating with the DDS via slow SPI, MASK_NU must be set to
        # perform serial transfer, then unset to propagate I/O update.
        self.toggle_mask_nu = self.cpld.io_update is not None
    
    @kernel
    def aligned_write_cfg_mask_nu(self, state):
        """Write NU_MASK of CFG at a coarse RTIO clock cycle.

        It aligns the time cursor to the next coarse time stamp, write NU_MASK
        to the Urukul CFG, then restore the initial fine time stamp.

        This method advances the time cursor by a CFG write duration, plus 1
        RTIO clock cycle."""
        fine_ts = now_mu() & (self.core.ref_multiplier - 1)
        delay_mu(self.core.ref_multiplier - fine_ts)
        self.cpld.cfg_mask_nu(self.dds.selected_ch, state)
        delay_mu(fine_ts)

    @kernel
    def pulse_mu(self, duration):
        """Unset MASK_NU, then pulse the IO Update TTL high for the specified
        duration (in machine units). MASK_NU is restored to the previous value
        after the I/O pulse.

        The I/O update TTL supports fine time stamp. Controlling I/O update
        through TTL requires Urukul CFG writes, but CFG writes does not
        support fine time stamps.

        Hence, a pair of preamble and postamble CFG writes (with coarse clock
        alignments) are issued to enable I/O updates from TTL temporarily.
        ``aligned_write_cfg_mask_nu`` implements the preamble/postamble writes.

        The time cursor is advanced by the sum of:
        - 2 CFG writes (enable/disable MASK_NU)
        - 2 coarse RTIO cycles (coarse clock alignment), and
        - I/O update pulse duration"""
        toggle_needed = bool((self.cpld.cfg_reg >> (urukul.ProtoRev9.CFG_MASK_NU + self.dds.selected_ch)) & 1)
        if self.toggle_mask_nu and toggle_needed:
            self.aligned_write_cfg_mask_nu(False)

        self.io_update.pulse_mu(duration)

        if self.toggle_mask_nu and toggle_needed:
            self.aligned_write_cfg_mask_nu(True)

    @kernel
    def pulse(self, duration):
        """Pulse the output high for the specified duration (in seconds).

        See pulse_mu."""
        toggle_needed = bool((self.cpld.cfg_reg >> (urukul.ProtoRev9.CFG_MASK_NU + self.dds.selected_ch)) & 1)
        if self.toggle_mask_nu and toggle_needed:
            self.aligned_write_cfg_mask_nu(False)

        self.io_update.pulse(duration)

        if self.toggle_mask_nu and toggle_needed:
            self.aligned_write_cfg_mask_nu(True)


class SyncDataUser:
    def __init__(self, core, sync_delay_seeds, io_update_delay):
        self.core = core
        self.sync_delay_seeds = sync_delay_seeds
        self.io_update_delay = io_update_delay

    @kernel
    def init(self):
        pass


class SyncDataEeprom:
    def __init__(self, dmgr, core, eeprom_str):
        self.core = core

        eeprom_device, eeprom_offset = eeprom_str.split(":")
        self.eeprom_device = dmgr.get(eeprom_device)
        self.eeprom_offset = int(eeprom_offset)

        self.sync_delay_seeds = [0] * 4
        self.io_update_delay = 0

    @kernel
    def init(self):
        word = self.eeprom_device.read_i32(self.eeprom_offset)
        for i in range(len(self.sync_delay_seeds)):
            self.sync_delay_seeds[i] = (word >> (i * 5)) & 0x1F
        io_update_delay = (word >> 20) & 0xFFF
        if io_update_delay == 0xFFF:    # unprogrammed EEPROM
            self.io_update_delay = 0
        else:
            self.io_update_delay = int32(io_update_delay)


class SharedDDS:
    """DDS configuration device for SU-Servo.

    Shared DDS device controls all 4 DDSes on the same Urukul device. Control
    of the 4 channels is multiplexed by selecting the corresponding MASK_NU
    bit prior to SPI transaction. IO_UPDATE is transferred by temporarily
    disabling the corresponding MASK_NU bit.

    :param cpld_device: Name of the Urukul CPLD this device is on.
    :param pll_n: DDS PLL multiplier. The DDS sample clock is
        ``f_ref / clk_div * pll_n`` where ``f_ref`` is the reference frequency and
        ``clk_div`` is the reference clock divider (both set in the parent
        Urukul CPLD instance).
    :param pll_en: PLL enable bit, set to 0 to bypass PLL (default: 1).
        Note that when bypassing the PLL the red front panel LED may remain on.
    :param pll_cp: DDS PLL charge pump setting.
    :param pll_vco: DDS PLL VCO range selection.
    :param sync_delay_seeds: ``SYNC_IN`` delays tuning starting value.
        To stabilize the ``SYNC_IN`` delays tuning, run :meth:`tune_sync_delays`
        once and set this to the delay tap number returned
        (default: [-1, -1, -1, -1] to signal no synchronization and no tuning
        during :meth:`init`).
        Can be a string of the form ``eeprom_device:byte_offset`` to read the
        value from a I2C EEPROM, in which case ``io_update_delay`` must be set
        to the same string value.
    :param io_update_delay: ``IO_UPDATE`` pulse alignment delay.
        To align ``IO_UPDATE`` to ``SYNC_CLK``,
        run :meth:`tune_io_update_group_delay` and set this to the delay tap
        number returned.
        Can be a string of the form ``eeprom_device:byte_offset`` to read the
        value from a I2C EEPROM, in which case ``sync_delay_seeds`` must be set
        to the same string value.
    :param core_device: Core device name
    """
    def __init__(self, dmgr, cpld_device,
                 pll_n=40, pll_cp=7, pll_vco=5, sync_delay_seeds=[-1, -1, -1, -1],
                 io_update_delay=0, pll_en=1, core_device="core"):
        self.core = dmgr.get(core_device)
        self.cpld = dmgr.get(cpld_device)
        self._inner_dds = ad9910.AD9910(dmgr, 3, cpld_device, pll_n=pll_n, pll_cp=pll_cp, pll_vco=pll_vco, pll_en=pll_en)

        self.selected_ch = 0
        self._inner_dds.io_update = _MaskedIOUpdate(self.core, self._inner_dds.cpld, self, self._inner_dds.io_update)

        if isinstance(sync_delay_seeds, str) or isinstance(io_update_delay, str):
            if sync_delay_seeds != io_update_delay:
                raise ValueError("When using EEPROM, sync_delay_seeds must be "
                                 "equal to io_update_delay")
            self.sync_data = SyncDataEeprom(dmgr, self.core, sync_delay_seeds)
        else:
            self.sync_data = SyncDataUser(self.core, sync_delay_seeds,
                                          io_update_delay)

    @portable
    def update_dds_sel(self, channel):
        """Select a specific DDS channel to accept I/O update"""
        self.cpld.cfg_mask_nu_all(1 << channel)
        self.selected_ch = channel

    @kernel
    def init(self, blind=False):
        """Initialize and configure the SU-Servo as a whole.

        See the :meth:`~artiq.coredevice.ad9910.AD9910.init` method of
        :class:`~artiq.coredevice.ad9910.AD9910` for AD9910 initialization.

        :param blind: Do not read back DDS identity and do not wait for lock.
            See :meth:`~artiq.coredevice.ad9910.AD9910.init`.
        """
        self.core.break_realtime()
        self.sync_data.init()
        for i in range(4):
            self.core.break_realtime()
            self.update_dds_sel(i)
            self.core.break_realtime()
            self._inner_dds.init(blind=blind, dds_channel_idx=i)

            if self.sync_data.sync_delay_seeds != [-1, -1, -1, -1]:
                self._inner_dds.tune_sync_delay(self.sync_data.sync_delay_seeds[i], dds_channel_idx=i)

        # Disable MASK_NU to resume QSPI
        self.cpld.cfg_mask_nu_all(0)

    @kernel
    def tune_sync_delays(self) -> TTuple([TInt32, TInt32, TInt32, TInt32]):
        """Find a set of stable ``SYNC_IN`` delays.

        This method first locates a set of ``SYNC_IN`` delays via
        :meth:`~artiq.coredevice.ad9910.AD9910.tune_sync_delay` of
        :class:`~artiq.coredevice.ad9910.AD9910`.

        This method and :meth:`tune_io_update_group_delay` can be run in any
        order.

        :return: Tuple of optimal delays.
        """
        def get_delay(ch) -> TInt32:
            self.core.break_realtime()
            self.update_dds_sel(ch)
            self.core.break_realtime()
            dly, _ = self._inner_dds.tune_sync_delay(dds_channel_idx=ch)
            return dly

        return get_delay(0), get_delay(1), get_delay(2), get_delay(3)

    @kernel
    def tune_io_update_group_delay(self) -> TInt32:
        """Find a stable ``IO_UPDATE`` delay alignment suitable for all DDS
        channels.

        Scan through increasing ``IO_UPDATE`` delays until a delay is found
        that lets ``IO_UPDATE`` be registered in the next ``SYNC_CLK`` cycle.
        Return an ``IO_UPDATE`` delay that does not coincide with any
        ``SYNC_CLK`` edges.

        This method assumes that the ``IO_UPDATE`` TTLOut device has one
        machine unit resolution (SERDES).

        This method and :meth:`tune_sync_delays` can be run in any order.

        :return: ``IO_UPDATE`` delay to be passed to the constructor
            :class:`~artiq.coredevice.urukul.CPLD` via the device database.
        """
        period = self._inner_dds.sysclk_per_mu * 4  # SYNC_CLK period
        sync_clk_offset = [ 0 for _ in range(period) ]
        repeat = 100
        for channel in range(4):
            self.update_dds_sel(channel)
            for i in range(period):
                t = 0
                # check whether the sync edge is strictly between i, i+2
                for j in range(repeat):
                    t += self._inner_dds.measure_io_update_alignment(int64(i), i + 2)
                if t != 0:  # no certain edge
                    continue
                # check left/right half: i,i+1 and i+1,i+2
                t1 = [0, 0]
                for j in range(repeat):
                    t1[0] += self._inner_dds.measure_io_update_alignment(int64(i), i + 1)
                    t1[1] += self._inner_dds.measure_io_update_alignment(int64(i + 1), i + 2)
                if ((t1[0] == 0 and t1[1] == 0) or
                        (t1[0] == repeat and t1[1] == repeat)):
                    # edge is not close to i + 1, can't interpret result
                    raise ValueError(
                        "no clear IO_UPDATE-SYNC_CLK alignment edge found")
                else:
                    sync_clk_offset[(i + 1) % period] += 1
                    break

        # Find an offset that isn't aligned by SYNC_CLK
        for i in range(period):
            if sync_clk_offset[i] == 0:
                return i

        raise ValueError("IO_UPDATE-SYNC_CLK alignment edges are too broad")

    @portable
    def frequency_to_ftw(self, frequency: TFloat) -> TInt32:
        """Return the 32-bit frequency tuning word corresponding to the given
        frequency."""
        return self._inner_dds.frequency_to_ftw(frequency)

    @portable
    def turns_to_pow(self, turns: TFloat) -> TInt32:
        """Return the 16-bit phase offset word corresponding to the given phase
        in turns."""
        return self._inner_dds.turns_to_pow(turns)
