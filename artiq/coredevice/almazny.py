from artiq.language.core import kernel, portable
from artiq.language.units import us

from numpy import int32


# almazny-specific data
ALMAZNY_LEGACY_REG_BASE = 0x0C
ALMAZNY_LEGACY_OE_SHIFT = 12

# higher SPI write divider to match almazny shift register timing 
# min SER time before SRCLK rise = 125ns
# -> div=32 gives 125ns for data before clock rise
# works at faster dividers too but could be less reliable
ALMAZNY_LEGACY_SPIT_WR = 32


class AlmaznyLegacy:
    """
    Almazny (High frequency mezzanine board for Mirny)

    This applies to Almazny hardware v1.1 and earlier.
    Use :class:`artiq.coredevice.almazny.AlmaznyChannel` for Almazny v1.2 and later.

    :param host_mirny: Mirny device Almazny is connected to
    """

    def __init__(self, dmgr, host_mirny):
        self.mirny_cpld = dmgr.get(host_mirny)
        self.att_mu = [0x3f] * 4
        self.channel_sw = [0] * 4
        self.output_enable = False

    @kernel
    def init(self):
        self.output_toggle(self.output_enable)

    @kernel
    def att_to_mu(self, att):
        """
        Convert an attenuator setting in dB to machine units.

        :param att: attenuator setting in dB [0-31.5]
        :return: attenuator setting in machine units
        """
        mu = round(att * 2.0)
        if mu > 63 or mu < 0:
            raise ValueError("Invalid Almazny attenuator settings!")
        return mu

    @kernel
    def mu_to_att(self, att_mu):
        """
        Convert a digital attenuator setting to dB.

        :param att_mu: attenuator setting in machine units
        :return: attenuator setting in dB
        """
        return att_mu / 2

    @kernel
    def set_att(self, channel, att, rf_switch=True):
        """
        Sets attenuators on chosen shift register (channel).

        :param channel: index of the register [0-3]
        :param att: attenuation setting in dBm [0-31.5]
        :param rf_switch: rf switch (bool)
        """
        self.set_att_mu(channel, self.att_to_mu(att), rf_switch)

    @kernel
    def set_att_mu(self, channel, att_mu, rf_switch=True):
        """
        Sets attenuators on chosen shift register (channel).

        :param channel: index of the register [0-3]
        :param att_mu: attenuation setting in machine units [0-63]
        :param rf_switch: rf switch (bool)
        """
        self.channel_sw[channel] = 1 if rf_switch else 0
        self.att_mu[channel] = att_mu
        self._update_register(channel)

    @kernel
    def output_toggle(self, oe):
        """
        Toggles output on all shift registers on or off.

        :param oe: toggle output enable (bool)
        """
        self.output_enable = oe
        cfg_reg = self.mirny_cpld.read_reg(1)
        en = 1 if self.output_enable else 0
        delay(100 * us)
        new_reg = (en << ALMAZNY_LEGACY_OE_SHIFT) | (cfg_reg & 0x3FF)
        self.mirny_cpld.write_reg(1, new_reg)
        delay(100 * us)

    @kernel
    def _flip_mu_bits(self, mu):
        # in this form MSB is actually 0.5dB attenuator
        # unnatural for users, so we flip the six bits
        return (((mu & 0x01) << 5)
                | ((mu & 0x02) << 3) 
                | ((mu & 0x04) << 1) 
                | ((mu & 0x08) >> 1) 
                | ((mu & 0x10) >> 3) 
                | ((mu & 0x20) >> 5))

    @kernel
    def _update_register(self, ch):
        self.mirny_cpld.write_ext(
            ALMAZNY_LEGACY_REG_BASE + ch, 
            8, 
            self._flip_mu_bits(self.att_mu[ch]) | (self.channel_sw[ch] << 6), 
            ALMAZNY_LEGACY_SPIT_WR
        )
        delay(100 * us)


class AlmaznyChannel:
    """
    One Almazny channel
    Almazny is a mezzanine for the Quad PLL RF source Mirny that exposes and
    controls the frequency-doubled outputs.
    This driver requires Almazny hardware revision v1.2 or later
    and Mirny CPLD gateware v0.3 or later.
    Use :class:`artiq.coredevice.almazny.AlmaznyLegacy` for Almazny hardware v1.1 and earlier.

    :param host_mirny: Mirny CPLD device name
    :param channel: channel index (0-3)
    """

    def __init__(self, dmgr, host_mirny, channel):
        self.channel = channel
        self.mirny_cpld = dmgr.get(host_mirny)

    @portable
    def to_mu(self, att, enable, led):
        """
        Convert an attenuation in dB, RF switch state and LED state to machine
        units.

        :param att: attenuator setting in dB (0-31.5)
        :param enable: RF switch state (bool)
        :param led: LED state (bool)
        :return: channel setting in machine units
        """
        mu = int32(round(att * 2.))
        if mu >= 64 or mu < 0:
            raise ValueError("Attenuation out of range")
        # unfortunate hardware design: bit reverse
        mu = ((mu & 0x15) << 1) | ((mu >> 1) & 0x15)
        mu = ((mu & 0x03) << 4) | (mu & 0x0c) | ((mu >> 4) & 0x03)
        if enable:
          mu |= 1 << 6
        if led:
          mu |= 1 << 7
        return mu

    @kernel
    def set_mu(self, mu):
        """
        Set channel state (machine units).

        :param mu: channel state in machine units.
        """
        self.mirny_cpld.write_ext(
            addr=0xc + self.channel, length=8, data=mu, ext_div=32)

    @kernel
    def set(self, att, enable, led=False):
        """
        Set attenuation, RF switch, and LED state (SI units).

        :param att: attenuator setting in dB (0-31.5)
        :param enable: RF switch state (bool)
        :param led: LED state (bool)
        """
        self.set_mu(self.to_mu(att, enable, led))
