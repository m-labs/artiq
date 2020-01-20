"""RTIO driver for Mirny (4 channel GHz PLLs)
"""

from artiq.language.core import kernel, delay
from artiq.language.units import us

from numpy import int32

from artiq.coredevice import spi2 as spi


SPI_CONFIG = (0*spi.SPI_OFFLINE | 0*spi.SPI_END |
              0*spi.SPI_INPUT | 1*spi.SPI_CS_POLARITY |
              0*spi.SPI_CLK_POLARITY | 0*spi.SPI_CLK_PHASE |
              0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX)

# SPI clock write and read dividers
SPIT_WR = 4
SPIT_RD = 16

SPI_CS = 1

WE = 1 << 24


class Mirny:
    """Mirny PLL-based RF generator.

    :param spi_device: SPI bus device
    :param core_device: Core device name (default: "core")
    """
    kernel_invariants = {"bus", "core"}

    def __init__(self, dmgr, spi_device, core_device="core"):
        self.core = dmgr.get(core_device)
        self.bus = dmgr.get(spi_device)

    @kernel
    def read_reg(self, addr):
        """Read a register"""
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_INPUT | spi.SPI_END, 24,
                               SPIT_RD, SPI_CS)
        self.bus.write((addr << 25))
        return self.bus.read() & int32(0xffff)

    @kernel
    def write_reg(self, addr, data):
        """Write a register"""
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END, 24, SPIT_WR, SPI_CS)
        self.bus.write((addr << 25) | WE | ((data & 0xffff) << 8))

    @kernel
    def init(self):
        """Initialize Mirny by reading the status register and verifying
        compatible hardware and protocol revisions"""
        reg0 = self.read_reg(0)
        if reg0 & 0b11 != 0b11:
            raise ValueError("Mirny HW_REV mismatch")
        if (reg0 >> 2) & 0b11 != 0b00:
            raise ValueError("Mirny PROTO_REV mismatch")
        delay(100*us)  # slack

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
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END, length,
                               SPIT_WR, SPI_CS)
        if length < 32:
            data <<= 32 - length
        self.bus.write(data)
