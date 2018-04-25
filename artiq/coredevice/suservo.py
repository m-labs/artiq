from artiq.language.core import kernel, delay, portable, now_mu
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
        self.set_config(0)
        delay(2*us)  # pipeline flush

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
        rtio_output(now_mu(), self.channel, addr | WE, value)
        delay_mu(self.ref_period_mu)

    @kernel
    def read(self, addr):
        rtio_output(now_mu(), self.channel, addr, 0)
        return rtio_input_data(self.channel)

    @kernel
    def set_config(self, start):
        self.write(CONFIG_ADDR, start)

    @kernel
    def get_status(self):
        return self.read(CONFIG_ADDR)

    @kernel
    def get_adc_mu(self, adc):
        return self.read(STATE_SEL | (adc << 1) | (1 << 8))

    @kernel
    def set_gain_mu(self, channel, gain):
        """Set instrumentation amplifier gain of a channel.

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


class Channel:
    kernel_invariants = {"channel", "core", "servo", "servo_channel"}

    def __init__(self, dmgr, channel, servo_device,
                 core_device="core"):
        self.core = dmgr.get(core_device)
        self.servo = dmgr.get(servo_device)
        self.channel = channel
        self.servo_channel = self.channel + 8 - self.servo.channel # FIXME

    @kernel
    def set(self, en_out, en_iir=0, profile=0):
        rtio_output(now_mu(), self.channel, 0,
                    en_out | (en_iir << 1) | (profile << 2))

    @kernel
    def set_profile_mu(self, profile, ftw, adc, offset,
                       a1, b0, b1, delay, pow=0):
        base = (self.servo_channel << 8) | (profile << 3)
        data = [ftw >> 16, b1, pow, adc | (delay << 8), offset, a1, ftw, b0]
        for i in range(8):
            self.servo.write(base + i, data[i])

    @kernel
    def get_profile_mu(self, profile, data):
        base = (self.servo_channel << 8) | (profile << 3)
        for i in range(8):
            data[i] = self.servo.read(base + i)
            delay(2*us)

    @kernel
    def get_asf_mu(self, profile):
        return self.servo.read(STATE_SEL | (self.servo_channel << 5) | profile)
