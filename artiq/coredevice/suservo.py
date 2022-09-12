from artiq.language.core import kernel, delay, delay_mu, portable
from artiq.language.units import us, ns
from artiq.language import *
from artiq.coredevice.rtio import rtio_output, rtio_input_data
from artiq.coredevice import spi2 as spi
from artiq.coredevice import urukul, sampler, ad9910
from math import ceil, log2
from numpy import int32, int64


COEFF_WIDTH = 18  # Must match gateware IIRWidths.coeff
Y_FULL_SCALE_MU = (1 << (COEFF_WIDTH - 1)) - 1
T_CYCLE = (2*(8 + 64) + 2)*8*ns  # Must match gateware Servo.t_cycle.
COEFF_SHIFT = 11  # Must match gateware IIRWidths.shift
PROFILE_WIDTH = 5  # Must match gateware IIRWidths.profile
FINE_TS_WIDTH = 3  # Must match gateware IIRWidths.ioup_dly


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
    8-channel ADC (Sampler) and any number of 4-channel DDS (Urukuls) with a
    DSP engine connecting the ADC data and the DDS output amplitudes to enable
    feedback. SU Servo can for example be used to implement intensity
    stabilization of laser beams with an amplifier and AOM driven by Urukul
    and a photodetector connected to Sampler.

    Additionally SU Servo supports multiple preconfigured profiles per channel
    and features like automatic integrator hold and coherent phase tracking.

    Notes:

        * See the SU Servo variant of the Kasli target for an example of how to
          connect the gateware and the devices. Sampler and each Urukul need
          two EEM connections.
        * Ensure that all Urukuls are AD9910 variants and have the on-board
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
    :param core_device: Core device name
    """
    kernel_invariants = {"channel", "core", "pgia", "cplds", "ddses",
                         "ref_period_mu", "num_channels", "coeff_sel",
                         "state_sel", "io_dly_addr", "config_addr",
                         "write_enable"}

    def __init__(self, dmgr, channel, pgia_device,
                 cpld_devices, dds_devices,
                 gains=0x0000, core_device="core"):

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
        assert self.ref_period_mu == self.core.ref_multiplier

        # The width of parts of the servo memory address depends on the number
        # of channels.
        self.num_channels = 4 * len(dds_devices)
        channel_width = ceil(log2(self.num_channels))
        coeff_depth = PROFILE_WIDTH + channel_width + 3
        self.io_dly_addr = 1 << (coeff_depth - 2)
        self.state_sel = 2 << (coeff_depth - 2)
        self.config_addr = 3 << (coeff_depth - 2)
        self.coeff_sel = 1 << coeff_depth
        self.write_enable = 1 << (coeff_depth + 1)

    @kernel
    def init(self):
        """Initialize the servo, Sampler and all Urukuls.

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

        for i in range(len(self.cplds)):
            cpld = self.cplds[i]
            dds = self.ddses[i]

            cpld.init(blind=True)
            prev_cpld_cfg = cpld.cfg_reg
            cpld.cfg_write(prev_cpld_cfg | (0xf << urukul.CFG_MASK_NU))
            dds.init(blind=True)

            if dds.sync_data.sync_delay_seed != -1:
                for channel_idx in range(4):
                    mask_nu_this = 1 << (urukul.CFG_MASK_NU + channel_idx)
                    cpld.cfg_write(prev_cpld_cfg | mask_nu_this)
                    delay(8 * us)
                    dds.tune_sync_delay(dds.sync_data.sync_delay_seed,
                                        cpld_channel_idx=channel_idx)
                    delay(50 * us)
            cpld.cfg_write(prev_cpld_cfg)

        self.set_io_update_delays(
            [dds.sync_data.io_update_delay for dds in self.ddses])

    @kernel
    def write(self, addr, value):
        """Write to servo memory.

        This method advances the timeline by one coarse RTIO cycle.

        :param addr: Memory location address.
        :param value: Data to be written.
        """
        addr |= self.write_enable
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
        self.write(self.config_addr, enable)

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
        :return: 17 bit signed X0
        """
        # State memory entries are 25 bits. Due to the pre-adder dynamic
        # range, X0/X1/OFFSET are only 24 bits. Finally, the RTIO interface
        # only returns the 18 MSBs (the width of the coefficient memory).
        return self.read(self.state_sel |
                         (2 * adc + (1 << PROFILE_WIDTH) * self.num_channels))

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

    @kernel
    def set_io_update_delays(self, dlys):
        """Set IO_UPDATE pulse alignment delays.

        :param dlys: List of delays for each Urukul
        """
        bits = 0
        mask_fine_ts = (1 << FINE_TS_WIDTH) - 1
        for i in range(len(dlys)):
            bits |= (dlys[i] & mask_fine_ts) << (FINE_TS_WIDTH * i)
        self.write(self.io_dly_addr, bits)


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
        self.servo_channel = (self.channel + 4 * len(self.servo.cplds) -
                              self.servo.channel)
        self.dds = self.servo.ddses[self.servo_channel // 4]

    @kernel
    def set(self, en_out, en_iir=0, profile=0, en_pt=0):
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
        :param en_pt: Coherent phase tracking enable
            * en_pt=1: "coherent phase mode"
            * en_pt=0: "continuous phase mode"
            (see :func:`artiq.coredevice.ad9910.AD9910.set_phase_mode` for a
            definition of the phase modes)
        """
        rtio_output(self.channel << 8,
                    en_out | (en_iir << 1) | (en_pt << 2) | (profile << 3))

    @kernel
    def set_reference_time(self):
        """Set reference time for "coherent phase mode" (see :meth:`set`).

        This method does not advance the timeline.
        With en_pt=1 (see :meth:`set`), the tracked DDS output phase of
        this channel will refer to the current timeline position.

        """
        fine_ts = now_mu() & ((1 << FINE_TS_WIDTH) - 1)
        rtio_output(self.channel << 8 | 1, self.dds.sysclk_per_mu * fine_ts)

    @kernel
    def set_dds_mu(self, profile, ftw, offs, pow_=0):
        """Set profile DDS coefficients in machine units.

        .. seealso:: :meth:`set_amplitude`

        :param profile: Profile number (0-31)
        :param ftw: Frequency tuning word (32 bit unsigned)
        :param offs: IIR offset (17 bit signed)
        :param pow_: Phase offset word (16 bit)
        """
        base = self.servo.coeff_sel | (self.servo_channel <<
                                       (3 + PROFILE_WIDTH)) | (profile << 3)
        self.servo.write(base + 0, ftw >> 16)
        self.servo.write(base + 6, (ftw & 0xffff))
        self.servo.write(base + 4, offs)
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
        ftw = self.dds.frequency_to_ftw(frequency)
        pow_ = self.dds.turns_to_pow(phase)
        offs = self.dds_offset_to_mu(offset)
        self.set_dds_mu(profile, ftw, offs, pow_)

    @kernel
    def set_dds_offset_mu(self, profile, offs):
        """Set only IIR offset in DDS coefficient profile.

        See :meth:`set_dds_mu` for setting the complete DDS profile.

        :param profile: Profile number (0-31)
        :param offs: IIR offset (17 bit signed)
        """
        base = self.servo.coeff_sel | (self.servo_channel <<
                                       (3 + PROFILE_WIDTH)) | (profile << 3)
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
    def set_dds_phase_mu(self, profile, pow_):
        """Set only POW in profile DDS coefficients.

        See :meth:`set_dds_mu` for setting the complete DDS profile.

        :param profile: Profile number (0-31)
        :param pow_: Phase offset word (16 bit)
        """
        base = self.servo.coeff_sel | (self.servo_channel <<
                                       (3 + PROFILE_WIDTH)) | (profile << 3)
        self.servo.write(base + 2, pow_)

    @kernel
    def set_dds_phase(self, profile, phase):
        """Set only phase in profile DDS coefficients.

        See :meth:`set_dds` for setting the complete DDS profile.

        :param profile: Profile number (0-31)
        :param phase: DDS phase in turns
        """
        self.set_dds_phase_mu(profile, self.dds.turns_to_pow(phase))

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
        base = self.servo.coeff_sel | (self.servo_channel <<
                                       (3 + PROFILE_WIDTH)) | (profile << 3)
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
        assert len(data) == 8
        base = self.servo.coeff_sel | (self.servo_channel <<
                                       (3 + PROFILE_WIDTH)) | (profile << 3)
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
        return self.servo.read(self.servo.state_sel | (
                self.servo_channel << PROFILE_WIDTH) | profile)

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
        self.servo.write(self.servo.state_sel | (
                self.servo_channel << PROFILE_WIDTH) | profile, y)

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
        if y_mu < 0 or y_mu > (1 << 17) - 1:
            raise ValueError("Invalid SUServo y-value!")
        self.set_y_mu(profile, y_mu)
        return y_mu


class CPLD(urukul.CPLD):
    """
    This module contains a subclass of the Urukul driver class in artiq.coredevice
    adapted to use CPLD read-back via half-duplex SPI. Only the 8 LSBs can be read
    back as the read-back buffer on the CPLD is 8 bits wide.
    """

    def __init__(self, dmgr, spi_device, io_update_device=None,
                 **kwargs):
        # Separate IO_UPDATE TTL output device used by SUServo core,
        # if active, else by artiq.coredevice.suservo.AD9910
        # :meth:`measure_io_update_alignment`.
        # The urukul.CPLD driver utilises the CPLD CFG register
        # option instead for pulsing IO_UPDATE of masked DDSs.
        self.io_update_ttl = dmgr.get(io_update_device)
        urukul.CPLD.__init__(self, dmgr, spi_device, **kwargs)

    @kernel
    def enable_readback(self):
        """
        This method sets the RB_EN flag in the Urukul CPLD configuration
        register. Once set, the CPLD expects an alternating sequence of
        two SPI transactions:

            * 1: Any transaction. If returning data, the 8 LSBs
                of that will be stored in the CPLD.

            * 2: One read transaction in half-duplex SPI mode shifting
                out data from the CPLD over MOSI (use :meth:`readback`).

        To end this protocol, call :meth:`disable_readback` during step 1.
        """
        self.cfg_write(self.cfg_reg | (1 << urukul.CFG_RB_EN))

    @kernel
    def disable_readback(self):
        """
        This method clears the RB_EN flag in the Urukul CPLD configuration
        register. This marks the end of the readback protocol (see
        :meth:`enable_readback`).
        """
        self.cfg_write(self.cfg_reg & ~(1 << urukul.CFG_RB_EN))

    @kernel
    def sta_read(self, full=False):
        """
        Read from status register

        :param full: retrieve status register by concatenating data from
            several readback transactions.
        """
        self.enable_readback()
        self.sta_read_impl()
        delay(16 * us)  # slack
        r = self.readback() << urukul.STA_RF_SW
        delay(16 * us)  # slack
        if full:
            self.enable_readback()  # dummy write
            r |= self.readback(urukul.CS_RB_PLL_LOCK) << urukul.STA_PLL_LOCK
            delay(16 * us)  # slack
            self.enable_readback()  # dummy write
            r |= self.readback(urukul.CS_RB_PROTO_REV) << urukul.STA_PROTO_REV
            delay(16 * us)  # slack
        self.disable_readback()
        return r

    @kernel
    def proto_rev_read(self):
        """Read 8 LSBs of proto_rev"""
        self.enable_readback()
        self.enable_readback()  # dummy write
        r = self.readback(urukul.CS_RB_PROTO_REV)
        self.disable_readback()
        return r

    @kernel
    def pll_lock_read(self):
        """Read PLL lock status"""
        self.enable_readback()
        self.enable_readback()  # dummy write
        r = self.readback(urukul.CS_RB_PLL_LOCK)
        self.disable_readback()
        return r & 0xf

    @kernel
    def get_att_mu(self):
        # Different behaviour to urukul.CPLD.get_att_mu: Here, the
        # latch enable of the attenuators activates 31.5dB
        # attenuation during the transactions.
        att_reg = int32(0)
        self.enable_readback()
        for i in range(4):
            self.core.break_realtime()
            self.bus.set_config_mu(urukul.SPI_CONFIG | spi.SPI_END, 8,
                                   urukul.SPIT_ATT_RD, urukul.CS_ATT)
            self.bus.write(0)  # shift in zeros, shift out next 8 bits
            r = self.readback() & 0xff
            att_reg |= r << (8 * i)

        delay(16 * us)  # slack
        self.disable_readback()

        self.att_reg = int32(att_reg)
        delay(8 * us)  # slack
        self.set_all_att_mu(self.att_reg)  # shift and latch current value again
        return self.att_reg

    @kernel
    def readback(self, cs=urukul.CS_RB_LSBS):
        """Read from the readback register in half-duplex SPI mode
        See :meth:`enable_readback` for usage instructions.

        :param cs: Select data to be returned from the readback register.
             - urukul.CS_RB_LSBS does not modify the readback register upon readback
             - urukul.CS_RB_PROTO_REV loads the 8 LSBs of proto_rev
             - urukul.CS_PLL_LOCK loads the PLL lock status bits concatenated with the
               IFC mode bits
        :return: CPLD readback register.
        """
        self.bus.set_config_mu(
            urukul.SPI_CONFIG | spi.SPI_END | spi.SPI_INPUT | spi.SPI_HALF_DUPLEX,
            8, urukul.SPIT_CFG_RD, cs)
        self.bus.write(0)
        return int32(self.bus.read())


class AD9910(ad9910.AD9910):
    """
    This module contains a subclass of the AD9910 driver class in artiq.coredevice
    using CPLD read-back via half-duplex SPI.
    """

    # Re-declare set of kernel invariants to avoid warning about non-existent
    # `sw` attribute, as the AD9910 (instance) constructor writes to the
    # class attributes.
    kernel_invariants = {
        "chip_select", "cpld", "core", "bus", "ftw_per_hz", "sysclk_per_mu"
    }

    @kernel
    def read32(self, addr):
        """ Read from a 32-bit register

        This method returns only the 8 LSBs of the return value.
        """
        self.cpld.enable_readback()
        self.read32_impl(addr)
        delay(12 * us)  # slack
        r = self.cpld.readback()
        delay(12 * us)  # slack
        self.cpld.disable_readback()
        return r

    @kernel
    def read64(self, addr):
        # 3-wire SPI transactions consisting of multiple transfers are not supported.
        raise NotImplementedError

    @kernel
    def read_ram(self, data):
        # 3-wire SPI transactions consisting of multiple transfers are not supported.
        raise NotImplementedError

    @kernel
    def measure_io_update_alignment(self, delay_start, delay_stop):
        """Use the digital ramp generator to locate the alignment between
        IO_UPDATE and SYNC_CLK.

        Refer to `artiq.coredevice.ad9910` :meth:`measure_io_update_alignment`.
        In order that this method can operate the io_update_ttl also used by the SUServo
        core, deactivate the servo before (see :meth:`set_config`).
        """
        # set up DRG
        self.set_cfr1(drg_load_lrr=1, drg_autoclear=1)
        # DRG -> FTW, DRG enable
        self.write32(ad9910._AD9910_REG_CFR2, 0x01090000)
        # no limits
        self.write64(ad9910._AD9910_REG_RAMP_LIMIT, -1, 0)
        # DRCTL=0, dt=1 t_SYNC_CLK
        self.write32(ad9910._AD9910_REG_RAMP_RATE, 0x00010000)
        # dFTW = 1, (work around negative slope)
        self.write64(ad9910._AD9910_REG_RAMP_STEP, -1, 0)
        # un-mask DDS
        cfg_masked = self.cpld.cfg_reg
        self.cpld.cfg_write(cfg_masked & ~(0xf << urukul.CFG_MASK_NU))
        delay(70 * us)  # slack
        # delay io_update after RTIO edge
        t = now_mu() + 8 & ~7
        at_mu(t + delay_start)
        # assumes a maximum t_SYNC_CLK period
        self.cpld.io_update_ttl.pulse(self.core.mu_to_seconds(16 - delay_start))  # realign
        # re-mask DDS
        self.cpld.cfg_write(cfg_masked)
        delay(10 * us)  # slack
        # disable DRG autoclear and LRR on io_update
        self.set_cfr1()
        delay(10 * us)  # slack
        # stop DRG
        self.write64(ad9910._AD9910_REG_RAMP_STEP, 0, 0)
        delay(10 * us)  # slack
        # un-mask DDS
        self.cpld.cfg_write(cfg_masked & ~(0xf << urukul.CFG_MASK_NU))
        at_mu(t + 0x20000 + delay_stop)
        self.cpld.io_update_ttl.pulse(self.core.mu_to_seconds(16 - delay_stop))  # realign
        # re-mask DDS
        self.cpld.cfg_write(cfg_masked)
        ftw = self.read32(ad9910._AD9910_REG_FTW)  # read out effective FTW
        delay(100*us)  # slack
        # disable DRG
        self.write32(ad9910._AD9910_REG_CFR2, 0x01010000)
        self.cpld.io_update.pulse(16 * ns)
        return ftw & 1
