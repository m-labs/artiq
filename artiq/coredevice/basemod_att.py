from artiq.language.core import kernel, portable, delay
from artiq.language.units import us, ms
from artiq.coredevice.shiftreg import ShiftReg


@portable
def to_mu(att):
    return round(att*2.0) ^ 0x3f

@portable
def from_mu(att_mu):
    return 0.5*(att_mu ^ 0x3f)


class BaseModAtt:
    def __init__(self, dmgr, rst_n, clk, le, mosi, miso):
        self.rst_n = dmgr.get(rst_n)
        self.shift_reg = ShiftReg(dmgr,
            clk=clk, ser=mosi, latch=le, ser_in=miso, n=8*4)

    @kernel
    def reset(self):
        # HMC's incompetence in digital design and interfaces means that
        # the HMC542 needs a level low on RST_N and then a rising edge
        # on Latch Enable. Their "latch" isn't a latch but a DFF.
        # Of course, it also powers up with a random attenuation, and
        # that cannot be fixed with simple pull-ups/pull-downs.
        self.rst_n.off()
        self.shift_reg.latch.off()
        delay(1*us)
        self.shift_reg.latch.on()
        delay(1*us)
        self.shift_reg.latch.off()
        self.rst_n.on()
        delay(1*us)

    @kernel
    def set_mu(self, att0, att1, att2, att3):
        """
        Sets the four attenuators on BaseMod.
        The values are in half decibels, between 0 (no attenuation)
        and 63 (31.5dB attenuation).
        """
        word = (
            (att0 <<  2) |
            (att1 << 10) | 
            (att2 << 18) | 
            (att3 << 26)
        )
        self.shift_reg.set(word)

    @kernel
    def get_mu(self):
        """
        Retrieves the current settings of the four attenuators on BaseMod.
        """
        word = self.shift_reg.get()
        att0 = (word >>  2) & 0x3f
        att1 = (word >> 10) & 0x3f
        att2 = (word >> 18) & 0x3f
        att3 = (word >> 26) & 0x3f
        return att0, att1, att2, att3

    @kernel
    def set(self, att0, att1, att2, att3):
        """
        Sets the four attenuators on BaseMod.
        The values are in decibels.
        """
        self.set_mu(to_mu(att0), to_mu(att1), to_mu(att2), to_mu(att3))

    @kernel
    def get(self):
        """
        Retrieves the current settings of the four attenuators on BaseMod.
        The values are in decibels.
        """
        att0, att1, att2, att3 = self.get_mu()
        return from_mu(att0), from_mu(att1), from_mu(att2), from_mu(att3)
