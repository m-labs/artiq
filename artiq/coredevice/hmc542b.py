from numpy import int32

from artiq.coredevice import spi2 as spi
from artiq.language.core import *
from artiq.language.types import *
from artiq.language.units import us


ATT_SPI_DIV = 5  # min 33 ns (30 MHz) - HMC542BLP4E datasheet (v00.1212)
ATT_SPI_CONFIG = (
    0 * spi.SPI_OFFLINE
    | 1 * spi.SPI_END
    | 0 * spi.SPI_INPUT
    | 0 * spi.SPI_CS_POLARITY
    | 0 * spi.SPI_CLK_POLARITY
    | 0 * spi.SPI_CLK_PHASE
    | 0 * spi.SPI_LSB_FIRST
    | 0 * spi.SPI_HALF_DUPLEX
)


class HMC542B:
    """Attenuator HMC542B driver

    :param spi_device: SPI bus device name.
    :param core_device: Core device name (default: "core").
    """

    kernel_invariants = {"core", "bus"}

    def __init__(self, dmgr, spi_device, core_device="core"):
        self.core = dmgr.get(core_device)
        self.bus = dmgr.get(spi_device)

    @portable(flags={"fast-math"})
    def att_to_mu(self, att):
        """Convert a digital step attenuator setting in dB to machine units.

        :param att: Attenuation in dB.
        :return: Digital attenuation setting in machine units.
        """
        mu = int32(0xFF) - int32(round(att * 8))
        if mu < 0 or mu > 0xFF:
            raise ValueError("Invalid Phaser attenuation!")
        return mu

    @portable(flags={"fast-math"})
    def mu_to_att(self, att_mu) -> TFloat:
        """Convert a digital step attenuator setting in machine units to dB.

        :param att_mu: Digital attenuation setting in machine units.
        :return: Attenuation in dB.
        """
        return (0xFF - att_mu) / 8

    @kernel
    def set_att_mu(self, att_mu):
        """Set digital step attenuator in machine units.

        :param att_mu: Digital attenuation setting in machine units.
        """
        self.bus.set_config_mu(ATT_SPI_CONFIG, 8, ATT_SPI_DIV, 1)
        self.bus.write(att_mu << 24)

    @kernel
    def get_att_mu(self) -> TInt32:
        """Get digital step attenuator in machine units.

        :return: Digital attenuation setting in machine units.
        """
        # shift in zeros to get current value
        self.bus.set_config_mu(ATT_SPI_CONFIG | spi.SPI_INPUT, 8, ATT_SPI_DIV, 1)
        self.bus.write(0)
        att_mu = self.bus.read() & 0xFF
        delay(40.0 * us)

        # shift it back
        self.bus.set_config_mu(ATT_SPI_CONFIG, 8, ATT_SPI_DIV, 1)
        self.bus.write(att_mu << 24)
        delay(40.0 * us)
        return att_mu

    @kernel
    def set_att(self, att):
        """Set digital step attenuator in SI units.

        :param att: Attenuation in dB.
        """
        self.set_att_mu(self.att_to_mu(att))

    @kernel
    def get_att(self):
        """Get digital step attenuator in SI units.

        :return: Attenuation in dB.
        """
        return self.mu_to_att(self.get_att_mu())
