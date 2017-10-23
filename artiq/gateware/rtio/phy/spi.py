from migen import *

from artiq.gateware.spi import SPIMaster as SPIMasterWB
from artiq.gateware.rtio.phy.wishbone import RT2WB


class SPIMaster(Module):
    def __init__(self, pads, pads_n=None, **kwargs):
        self.submodules._ll = ClockDomainsRenamer("rio_phy")(
            SPIMasterWB(pads, pads_n, **kwargs))
        self.submodules._rt2wb = RT2WB(2, self._ll.bus)
        self.rtlink = self._rt2wb.rtlink
        self.probes = []
