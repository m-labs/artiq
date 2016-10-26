from collections import namedtuple

from migen import *
from artiq.gateware.rtio import rtlink

from artiq.gateware.dsp.sawg import Channel as _Channel


_Phy = namedtuple("Phy", "rtlink probes overrides")

_ChannelPHY = ClockDomainsRenamer("rio_phy")(_Channel)


class Channel(_ChannelPHY):
    def __init__(self, *args, **kwargs):
        _ChannelPHY.__init__(self, *args, **kwargs)
        self.phys = []
        for i in self.i:
            rl = rtlink.Interface(rtlink.OInterface(
                min(32, len(i.payload))))  # TODO: test/expand
            self.comb += [
                i.stb.eq(rl.o.stb),
                rl.o.busy.eq(~i.ack),
                Cat(i.payload.flatten()).eq(rl.o.data),
            ]
            # no probes, overrides
            self.phys.append(_Phy(rl, [], []))
        self.phys_names = dict(zip("cfg f0 p0 a1 f1 p1 a2 f2 p2".split(),
                                   self.phys))
