from collections import namedtuple

from migen import *
from artiq.gateware.rtio import rtlink

from artiq.gateware.dsp.sawg import DDSFast


_Phy = namedtuple("Phy", "rtlink probes overrides")

DDSFast_rtio = ClockDomainsRenamer("rio_phy")(DDSFast)


class Channel(DDSFast_rtio):
    def __init__(self, *args, **kwargs):
        DDSFast_rtio.__init__(self, *args, **kwargs)
        self.phys = []
        for i in self.i:
            rl = rtlink.Interface(rtlink.OInterface(len(i.payload)))
            self.comb += [
                i.stb.eq(rl.o.stb),
                rl.o.busy.eq(~i.ack),
                Cat(i.payload.flatten()).eq(rl.o.data),
            ]
            # no probes, overrides
            self.phys.append(_Phy(rl, [], []))
        self.phys_names = dict(zip("afp", self.phys))
