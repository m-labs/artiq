from artiq.language.core import kernel, syscall
from artiq.language.types import TInt32, TNone


@syscall(flags={"nounwind", "nowrite"})
def ad9154_init() -> TNone:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nounwind", "nowrite"})
def ad9154_write(addr: TInt32, data: TInt32) -> TNone:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nounwind", "nowrite"})
def ad9154_read(addr: TInt32) -> TInt32:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nounwind", "nowrite"})
def ad9516_write(addr: TInt32, data: TInt32) -> TNone:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nounwind", "nowrite"})
def ad9516_read(addr: TInt32) -> TInt32:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nounwind", "nowrite"})
def ad9154_jesd_enable(en: TInt32) -> TNone:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nounwind", "nowrite"})
def ad9154_jesd_ready() -> TInt32:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nounwind", "nowrite"})
def ad9154_jesd_prbs(prbs: TInt32) -> TNone:
    raise NotImplementedError("syscall not simulated")


class AD9154:
    """AD9154-FMC-EBZ SPI support

    There are two devices on the SPI bus, a AD9154 DAC and a AD9516 clock
    divider/fanout.

    Register and bit names are in :mod:`artiq.coredevice.ad9154_reg` and
    :mod:`artiq.coredevice.ad9516_reg` respectively.

    The SPI bus does not operate over RTIO but directly. This class does not
    interact with the timeline.
    """
    def __init__(self, dmgr, core_device="core"):
        self.core = dmgr.get(core_device)

    @kernel
    def init(self):
        """Initialize and configure the SPI bus."""
        ad9154_init()

    @kernel
    def dac_write(self, addr, data):
        """Write `data` to AD9154 SPI register at `addr`."""
        ad9154_write(addr, data)

    @kernel
    def dac_read(self, addr):
        """Read AD9154 SPI register at `addr`."""
        return ad9154_read(addr)

    @kernel
    def clock_write(self, addr, data):
        """Write `data` to AD9516 SPI register at `addr`."""
        ad9516_write(addr, data)

    @kernel
    def clock_read(self, addr):
        """Read AD9516 SPI register at `addr`."""
        return ad9516_read(addr)

    @kernel
    def jesd_enable(self, en):
        """Enables the JESD204B core startup sequence."""
        ad9154_jesd_enable(en)

    @kernel
    def jesd_ready(self):
        """Returns `True` if the JESD links are up."""
        return ad9154_jesd_ready()

    @kernel
    def jesd_prbs(self, prbs):
        ad9154_jesd_prbs(prbs)
