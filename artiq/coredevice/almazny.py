from artiq.language.core import kernel, portable

from numpy import int32


class AlmaznyChannel:
    """
    One Almazny channel

    Almazny is a mezzanine for the Quad PLL RF source Mirny that exposes and
    controls the frequency-doubled outputs.

    This driver requires Almazny hardware revision v1.2 or later
    and Mirny CPLD gateware v0.3 or later.

    Use :class:`artiq.coredevice.mirny.Almazny` for Almazny hardware v1.1 and earlier.

    :param cpld_device: Mirny CPLD device name
    :param channel: channel index (0-3)
    """

    def __init__(self, dmgr, cpld_device, channel):
        self.channel = channel
        self.cpld = dmgr.get(cpld_device)

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
        self.cpld.write_ext(
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
