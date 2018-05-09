from artiq.language.core import kernel, delay, portable, now_mu, delay_mu
from artiq.language.units import us, ms
from artiq.coredevice.rtio import rtio_output, rtio_input_data

from numpy import int32, int64

from artiq.coredevice import spi2 as spi
from artiq.coredevice import urukul, sampler


COEFF_WIDTH = 18
COEFF_DEPTH = 10 + 1
WE = 1 << COEFF_DEPTH + 1
STATE_SEL = 1 << COEFF_DEPTH
CONFIG_SEL = 1 << COEFF_DEPTH - 1
CONFIG_ADDR = CONFIG_SEL | STATE_SEL


class SUServo:
    kernel_invariants = {"channel", "core", "pgia", "cpld0", "cpld1",
                         "dds0", "dds1", "ref_period_mu"}

    def __init__(self, dmgr, channel, pgia_device,
                 cpld0_device, cpld1_device,
                 dds0_device, dds1_device,
                 core_device="core"):

        self.core = dmgr.get(core_device)
        self.pgia = dmgr.get(pgia_device)
        self.dds0 = dmgr.get(dds0_device)
        self.dds1 = dmgr.get(dds1_device)
        self.cpld0 = dmgr.get(cpld0_device)
        self.cpld1 = dmgr.get(cpld1_device)
        self.channel = channel
        self.gains = 0x0000
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
        self.set_config(0)
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
        """Get an ADC reading (IIR filter input X0).

        This method does not advance the timeline but consumes all slack.

        :param adc: ADC channel number (0-7)
        :return: 16 bit signed Y0
        """
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
    def get_adc(self, adc):
        raise NotImplementedError  # FIXME


class Channel:
    kernel_invariants = {"channel", "core", "servo", "servo_channel"}

    def __init__(self, dmgr, channel, servo_device,
                 core_device="core"):
        self.core = dmgr.get(core_device)
        self.servo = dmgr.get(servo_device)
        self.channel = channel
        # FIXME: this assumes the mem channel is right after the control
        # channels
        self.servo_channel = self.channel + 8 - self.servo.channel

    @kernel
    def set(self, en_out, en_iir=0, profile=0):
        """Operate channel.

        This method does not advance the timeline.

        :param en_out: RF switch enable
        :param en_iir: IIR updates enable
        :param profile: Active profile (0-31)
        """
        rtio_output(now_mu(), self.channel, 0,
                    en_out | (en_iir << 1) | (profile << 2))

    @kernel
    def set_dds_mu(self, profile, ftw, offset, pow=0):
        """Set profile DDS coefficients.

        This method advances the timeline by four Servo memory accesses.

        :param profile: Profile number (0-31)
        :param ftw: Frequency tuning word (32 bit unsigned)
        :param offset: IIR offset (setpoint)
        :param pow: Phase offset word (16 bit unsigned)
        """
        base = (self.servo_channel << 8) | (profile << 3)
        self.servo.write(base + 0, ftw >> 16)
        self.servo.write(base + 6, ftw)
        self.servo.write(base + 4, offset)
        self.servo.write(base + 2, pow)

    @kernel
    def set_dds(self, profile, frequency, offset, phase=0.):
        raise NotImplementedError  # FIXME

    @kernel
    def set_iir_mu(self, profile, adc, a1, b0, b1, delay=0):
        """Set profile IIR coefficients.

        This method advances the timeline by four Servo memory accesses.

        :param profile: Profile number (0-31)
        :param adc: ADC channel to use (0-7)
        :param a1: 18 bit signed A1 coefficient (Y1 coefficient,
            feedback, integrator gain)
        :param b0: 18 bit signed B0 coefficient (recent,
            X0 coefficient, feed forward, proportional gain)
        :param b1: 18 bit signed B1 coefficient (old,
            X1 coefficient, feed forward, proportional gain)
        :param delay: Number of Servo cycles (~1.1 µs each) to suppress
            IIR updates for after either (1) enabling or disabling RF output,
            (2) enabling or disabling IIR updates, or (3) setting the active
            profile number: i.e. after invoking :meth:`set`.
        """
        base = (self.servo_channel << 8) | (profile << 3)
        self.servo.write(base + 1, b1)
        self.servo.write(base + 3, adc | (delay << 8))
        self.servo.write(base + 5, a1)
        self.servo.write(base + 7, b0)

    @kernel
    def set_iir(self, profile, adc, i_gain, p_gain, delay=0.):
        raise NotImplementedError  # FIXME

    @kernel
    def get_profile_mu(self, profile, data):
        """Retrieve profile data.

        The data is returned in the `data` argument as:
        `[ftw >> 16, b1, pow, adc | (delay << 8), offset, a1, ftw, b0]`.

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
        """Get a profile's IIR state (filter output, Y0).

        The IIR state is also know as the "integrator", or the DDS amplitude
        scale factor. It is 18 bits wide and unsigned.

        This method does not advance the timeline but consumes all slack.

        :param profile: Profile number (0-31)
        :return: 18 bit unsigned Y0
        """
        return self.servo.read(STATE_SEL | (self.servo_channel << 5) | profile)

    @kernel
    def get_y(self, profile):
        raise NotImplementedError  # FIXME

    @kernel
    def set_y_mu(self, profile, y):
        """Set a profile's IIR state (filter output, Y0).

        The IIR state is also know as the "integrator", or the DDS amplitude
        scale factor. It is 18 bits wide and unsigned.

        This method must not be used when the Servo
        could be writing to the same location. Either deactivate the profile,
        or deactivate IIR updates, or disable Servo iterations.

        This method advances the timeline by one Servo memory access.

        :param profile: Profile number (0-31)
        :param y: 18 bit unsigned Y0
        """
        return self.servo.write(
            STATE_SEL | (self.servo_channel << 5) | profile, y)

    @kernel
    def set_y(self, profile, y):
        raise NotImplementedError  # FIXME
