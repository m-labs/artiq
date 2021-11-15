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
ALMAZNY_SER_MOSI = 0
ALMAZNY_SER_CLK = 1
ALMAZNY_REG_LATCH_BASE = 2
ALMAZNY_REG_CLEAR = 6

# mirny/almazny mezz io reg address
ALMAZNY_MEZZIO_REG = 0x03


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

    :param mirny - Mirny device Almazny is connected to
    """

    def __init__(self, dmgr, host_mirny):
        self.mirny = dmgr.get(host_mirny)
        self.mezz_data = 0

    @kernel
    def init(self):
        self._send_mezz_data([
            (ALMAZNY_REG_CLEAR, 1),
            (ALMAZNY_REG_LATCH_BASE+0, 0),
            (ALMAZNY_REG_LATCH_BASE+1, 0),
            (ALMAZNY_REG_LATCH_BASE+2, 0),
            (ALMAZNY_REG_LATCH_BASE+3, 0),
            (ALMAZNY_SER_CLK, 0)
            ])

    @kernel
    def reg_set(self, reg_i, attin1=1, attin2=1, attin3=1, attin4=1, attin5=1, attin6=1, output_on=0):
        """
        Sets the data on chosen shift register.
        :param reg_i - index of the register [1-4]
        :param attin[1-6] - attenuator on {0, 1} 
        :attin1 - 16dB attenuator, att6 - 0.5dB
        :param output_on - RF output on {0, 1}
        """
        shift_reg = [0, output_on, attin6, attin5, attin4, attin3, attin2, attin1]
        if not 4 >= reg_i >= 1:
            raise ValueError("register must be 1, 2, 3 or 4")
        self._send_mezz_data([
            (ALMAZNY_REG_LATCH_BASE + (reg_i - 1), 0)
        ])
        for val in shift_reg:
            self._cycle([
                (ALMAZNY_SER_MOSI, val) 
            ])
        self._latch(reg_i)

    @kernel
    def reg_clear(self, reg_i):
        """
        Clears content of a register.
        :param reg_i - index of the register [1-4]
        """
        if not 4 >= reg_i >= 1:
            raise ValueError("register must be 1, 2, 3 or 4")
        self._send_mezz_data([
            (ALMAZNY_REG_CLEAR, 0),
            (ALMAZNY_REG_LATCH_BASE + (reg_i - 1), 0)
        ])
        self._send_mezz_data([
            (ALMAZNY_REG_CLEAR, 0),
            (ALMAZNY_REG_LATCH_BASE + (reg_i - 1), 1)
        ])
        self._send_mezz_data([
            (ALMAZNY_REG_CLEAR, 1),
            (ALMAZNY_REG_LATCH_BASE + (reg_i - 1), 0)
        ])

    @kernel
    def reg_clear_all(self):
        """
        Clears all registers.
        """
        self._send_mezz_data([
            (ALMAZNY_REG_CLEAR, 0),
            (ALMAZNY_REG_LATCH_BASE, 0),
            (ALMAZNY_REG_LATCH_BASE + 1, 0),
            (ALMAZNY_REG_LATCH_BASE + 2, 0),
            (ALMAZNY_REG_LATCH_BASE + 3, 0),
        ])
        self._send_mezz_data([
            (ALMAZNY_REG_CLEAR, 0),
            (ALMAZNY_REG_LATCH_BASE, 1),
            (ALMAZNY_REG_LATCH_BASE + 1, 1),
            (ALMAZNY_REG_LATCH_BASE + 2, 1),
            (ALMAZNY_REG_LATCH_BASE + 3, 1),
        ])
        self._send_mezz_data([
            (ALMAZNY_REG_CLEAR, 1),
            (ALMAZNY_REG_LATCH_BASE, 0),
            (ALMAZNY_REG_LATCH_BASE + 1, 0),
            (ALMAZNY_REG_LATCH_BASE + 2, 0),
            (ALMAZNY_REG_LATCH_BASE + 3, 0),
        ])

    @kernel
    def _cycle(self, data):
        """
        one cycle for inputting register data
        """
        self._send_mezz_data([
            (ALMAZNY_SER_CLK, 0),
        ] + data)
        self._send_mezz_data([
            (ALMAZNY_SER_CLK, 1),
        ] + data)

    @kernel
    def _latch(self, reg_i):
        self._send_mezz_data([
            (ALMAZNY_SER_CLK, 0),
            (ALMAZNY_REG_LATCH_BASE + (reg_i - 1), 1)
        ])
        self._send_mezz_data([
            (ALMAZNY_REG_LATCH_BASE + (reg_i - 1), 0)
        ])

    @kernel
    def put_data(self, pin, d):
        if d not in [0, 1]:
            raise ValueError("Data can be only 0 or 1")
        self.mezz_data = (self.mezz_data & ~(1 << pin)) | d << pin  # data
        self.mezz_data |= 1 << pin + 8  # oe

    @kernel
    def _send_mezz_data(self, pins_data):
        """
        Sends the raw data to the mezzanine board.
        :param pins_data - list of tuples in format (pin_number, bit)
        """
        for pin, data in pins_data:
            self.put_data(pin, data)
        self.mirny.write_reg(ALMAZNY_MEZZIO_REG, self.mezz_data)
        # delay to ensure the data has been read by the SR
        delay(1*us)
