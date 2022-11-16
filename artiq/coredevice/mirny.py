"""RTIO driver for Mirny (4 channel GHz PLLs)
"""

from artiq.language.core import kernel, delay, portable
from artiq.language.units import us

from numpy import int32

from artiq.coredevice import spi2 as spi


SPI_CONFIG = (
    0 * spi.SPI_OFFLINE
    | 0 * spi.SPI_END
    | 0 * spi.SPI_INPUT
    | 1 * spi.SPI_CS_POLARITY
    | 0 * spi.SPI_CLK_POLARITY
    | 0 * spi.SPI_CLK_PHASE
    | 0 * spi.SPI_LSB_FIRST
    | 0 * spi.SPI_HALF_DUPLEX
)

# SPI clock write and read dividers
SPIT_WR = 4
SPIT_RD = 16

SPI_CS = 1

WE = 1 << 24

# supported CPLD code version
PROTO_REV_MATCH = 0x0

# almazny-specific data
ALMAZNY_REG_BASE = 0x0C
ALMAZNY_OE_SHIFT = 12

# higher SPI write divider to match almazny shift register timing 
# min SER time before SRCLK rise = 125ns
# -> div=32 gives 125ns for data before clock rise
# works at faster dividers too but could be less reliable
ALMAZNY_SPIT_WR = 32


class Mirny:
    """
    Mirny PLL-based RF generator.

    :param spi_device: SPI bus device
    :param refclk: Reference clock (SMA, MMCX or on-board 100 MHz oscillator)
        frequency in Hz
    :param clk_sel: Reference clock selection.
        Valid options are: "XO" - onboard crystal oscillator;
        "SMA" - front-panel SMA connector; "MMCX" - internal MMCX connector.
        Passing an integer writes it as ``clk_sel`` in the CPLD's register 1.
        The effect depends on the hardware revision.
    :param core_device: Core device name (default: "core")
    """

    kernel_invariants = {"bus", "core", "refclk", "clk_sel_hw_rev"}

    def __init__(self, dmgr, spi_device, refclk=100e6, clk_sel="XO", core_device="core"):
        self.core = dmgr.get(core_device)
        self.bus = dmgr.get(spi_device)

        # reference clock frequency
        self.refclk = refclk
        if not (10 <= self.refclk / 1e6 <= 600):
            raise ValueError("Invalid refclk")

        # reference clock selection
        try:
            self.clk_sel_hw_rev = {
            # clk source: [reserved, reserved, v1.1, v1.0]
                "xo": [-1, -1, 0, 0],
                "mmcx": [-1, -1, 3, 2],
                "sma": [-1, -1, 2, 3],
            }[clk_sel.lower()]
        except AttributeError:  # not a string, fallback to int
            if clk_sel & 0x3 != clk_sel:
                raise ValueError("Invalid clk_sel") from None
            self.clk_sel_hw_rev = [clk_sel] * 4
        except KeyError:
            raise ValueError("Invalid clk_sel") from None

        self.clk_sel = -1

        # board hardware revision
        self.hw_rev = 0  # v1.0: 3, v1.1: 2

        # TODO: support clk_div on v1.0 boards

    @kernel
    def read_reg(self, addr):
        """Read a register"""
        self.bus.set_config_mu(
            SPI_CONFIG | spi.SPI_INPUT | spi.SPI_END, 24, SPIT_RD, SPI_CS
        )
        self.bus.write((addr << 25))
        return self.bus.read() & int32(0xFFFF)

    @kernel
    def write_reg(self, addr, data):
        """Write a register"""
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END, 24, SPIT_WR, SPI_CS)
        self.bus.write((addr << 25) | WE | ((data & 0xFFFF) << 8))

    @kernel
    def init(self, blind=False):
        """
        Initialize and detect Mirny.

        Select the clock source based the board's hardware revision.
        Raise ValueError if the board's hardware revision is not supported.

        :param blind: Verify presence and protocol compatibility. Raise ValueError on failure.
        """
        reg0 = self.read_reg(0)
        self.hw_rev = reg0 & 0x3

        if not blind:
            if (reg0 >> 2) & 0x3 != PROTO_REV_MATCH:
                raise ValueError("Mirny PROTO_REV mismatch")
            delay(100 * us)  # slack

        # select clock source
        self.clk_sel = self.clk_sel_hw_rev[self.hw_rev]

        if self.clk_sel < 0:
            raise ValueError("Hardware revision not supported")

        self.write_reg(1, (self.clk_sel << 4))
        delay(1000 * us)

    @portable(flags={"fast-math"})
    def att_to_mu(self, att):
        """Convert an attenuation setting in dB to machine units.

        :param att: Attenuation setting in dB.
        :return: Digital attenuation setting.
        """
        code = int32(255) - int32(round(att * 8))
        if code < 0 or code > 255:
            raise ValueError("Invalid Mirny attenuation!")
        return code

    @kernel
    def set_att_mu(self, channel, att):
        """Set digital step attenuator in machine units.

        :param att: Attenuation setting, 8 bit digital.
        """
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END, 16, SPIT_WR, SPI_CS)
        self.bus.write(((channel | 8) << 25) | (att << 16))

    @kernel
    def set_att(self, channel, att):
        """Set digital step attenuator in SI units.

        This method will write the attenuator settings of the selected channel.

        .. seealso:: :meth:`set_att_mu`

        :param channel: Attenuator channel (0-3).
        :param att: Attenuation setting in dB. Higher value is more
            attenuation. Minimum attenuation is 0*dB, maximum attenuation is
            31.5*dB.
        """
        self.set_att_mu(channel, self.att_to_mu(att))

    @kernel
    def write_ext(self, addr, length, data, ext_div=SPIT_WR):
        """Perform SPI write to a prefixed address"""
        self.bus.set_config_mu(SPI_CONFIG, 8, SPIT_WR, SPI_CS)
        self.bus.write(addr << 25)
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END, length, ext_div, SPI_CS)
        if length < 32:
            data <<= 32 - length
        self.bus.write(data)


class Almazny:
    """
    Almazny (High frequency mezzanine board for Mirny)

    :param host_mirny - Mirny device Almazny is connected to
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
        :param channel - index of the register [0-3]
        :param att_mu - attenuation setting in dBm [0-31.5]
        :param rf_switch - rf switch (bool)
        """
        self.set_att_mu(channel, self.att_to_mu(att), rf_switch)

    @kernel
    def set_att_mu(self, channel, att_mu, rf_switch=True):
        """
        Sets attenuators on chosen shift register (channel).
        :param channel - index of the register [0-3]
        :param att_mu - attenuation setting in machine units [0-63]
        :param rf_switch - rf switch (bool)
        """
        self.channel_sw[channel] = 1 if rf_switch else 0
        self.att_mu[channel] = att_mu
        self._update_register(channel)

    @kernel
    def output_toggle(self, oe):
        """
        Toggles output on all shift registers on or off.
        :param oe - toggle output enable (bool)
        """
        self.output_enable = oe
        cfg_reg = self.mirny_cpld.read_reg(1)
        en = 1 if self.output_enable else 0
        delay(100 * us)
        new_reg = (en << ALMAZNY_OE_SHIFT) | (cfg_reg & 0x3FF)
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
            ALMAZNY_REG_BASE + ch, 
            8, 
            self._flip_mu_bits(self.att_mu[ch]) | (self.channel_sw[ch] << 6), 
            ALMAZNY_SPIT_WR
        )
        delay(100 * us)

    @kernel
    def _update_all_registers(self):
        for i in range(4):
            self._update_register(i)