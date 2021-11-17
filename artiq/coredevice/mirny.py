"""RTIO driver for Mirny (4 channel GHz PLLs)
"""

from artiq.language.core import kernel, delay
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

# almazny mezzio pin map
ALMAZNY_SER_MOSI = 0x01
ALMAZNY_SER_CLK = 0x02
ALMAZNY_REG_LATCH_BASE = 0x04
ALMAZNY_REG_CLEAR = 0x40

# mirny/almazny mezz io reg address
ALMAZNY_MEZZIO_REG = 0x03

ALMAZNY_OE_MASK = 0xFF00


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

    @kernel
    def set_att_mu(self, channel, att):
        """Set digital step attenuator in machine units.

        :param att: Attenuation setting, 8 bit digital.
        """
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END, 16, SPIT_WR, SPI_CS)
        self.bus.write(((channel | 8) << 25) | (att << 16))

    @kernel
    def write_ext(self, addr, length, data):
        """Perform SPI write to a prefixed address"""
        self.bus.set_config_mu(SPI_CONFIG, 8, SPIT_WR, SPI_CS)
        self.bus.write(addr << 25)
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END, length, SPIT_WR, SPI_CS)
        if length < 32:
            data <<= 32 - length
        self.bus.write(data)


class Almazny:
    """
    Almazny (High frequency mezzanine board for Mirny)

    :param host_mirny - Mirny device Almazny is connected to
    """

    def __init__(self, dmgr, host_mirny):
        self.mirny = dmgr.get(host_mirny)
        self.att_mu = [0x3f] * 4
        self.rf_switches = [0] * 4

    @kernel
    def init(self):
        self._send_mezz_data(ALMAZNY_REG_CLEAR)  # reset the rest

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
    def set_att_mu(self, channel, att_mu):
        """
        Sets attenuators on chosen shift register (channel).
        :param channel - index of the register [0-3]
        :param att_mu - attenuation setting in machine units [0-63]
        """
        if not 3 >= channel >= 0:
            raise ValueError("channel must be 0, 1, 2 or 3")
        if not 63 >= att_mu >= 0:
            raise ValueError("Invalid Almazny attenuator setting")

        self.att_mu[channel] = att_mu
        self._update_register(channel)

    @kernel
    def cfg_sw(self, channel, rf_on):
        """
        Toggles RF switch on or off.
        :param channel - index of the channel [0-3]
        :param rf_on - RF output on (bool)
        """
        if not 3 >= channel >= 0:
            raise ValueError("channel must be 0, 1, 2 or 3")
        self.rf_switches[channel] = 1 if rf_on else 0
        self._update_register(channel)

    @kernel
    def cfg_sw_all(self, rf_on):
        """
        Toggles all RF switches on or off.
        :param rf_on - RF output on (bool)
        """
        for i in range(4):
            self.rf_switches[i] = 1 if rf_on else 0
        self._update_all_registers()

    @kernel
    def reg_clear(self, channel):
        """
        Clears content of a register.
        :param channel - index of the channel [0-3]
        """
        if not 3 >= channel >= 0:
            raise ValueError("channel must be 0, 1, 2 or 3")
        self._send_mezz_data(0)  # reg_clear and latch are 0
        self._send_mezz_data(ALMAZNY_REG_LATCH_BASE << channel)  # just latch is 1
        self._send_mezz_data(ALMAZNY_REG_CLEAR)  # clear is back to 1

    @kernel
    def reg_clear_all(self):
        """
        Clears all registers.
        """
        self._send_mezz_data(0)  # reg clear and everything at 0
        self._send_mezz_data(ALMAZNY_REG_LATCH_BASE |
                             ALMAZNY_REG_LATCH_BASE << 1 |
                             ALMAZNY_REG_LATCH_BASE << 2 |
                             ALMAZNY_REG_LATCH_BASE << 3
                            )
        self._send_mezz_data(ALMAZNY_REG_CLEAR)

    @kernel
    def _cycle(self, data):
        """
        one cycle for inputting register data
        """
        self._send_mezz_data(ALMAZNY_REG_CLEAR | data)  # clk = 0
        self._send_mezz_data(ALMAZNY_REG_CLEAR | ALMAZNY_SER_CLK | data)

    @kernel
    def _latch(self, ch):
        self._send_mezz_data(ALMAZNY_REG_CLEAR | 
                             ALMAZNY_SER_CLK |
                             ALMAZNY_REG_LATCH_BASE << ch)
        self._send_mezz_data(ALMAZNY_REG_CLEAR)  # reset latch

    @kernel
    def _update_register(self, ch):
        self._send_mezz_data(ALMAZNY_REG_CLEAR)  # reset all latches
        self._cycle(0)  # initial 0 (unused value)
        self._cycle(self.rf_switches[ch])
        for i in range(6):  # data
            self._cycle((self.att_mu[ch] >> i) & 0x01)
        self._latch(ch)

    @kernel
    def _update_all_registers(self):
        for i in range(4):
            self._update_register(i)

    @kernel
    def _send_mezz_data(self, data):
        """
        Sends the raw data to the mezzanine board.
        :param data - data to send over
        """
        self.mirny.write_reg(ALMAZNY_MEZZIO_REG, ALMAZNY_OE_MASK | data)
        # delay to ensure the data has been read by the SR
        delay(1*us)
