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
            rl = rtlink.Interface(rtlink.OInterface(len(i.payload),
                                                    delay=-i.latency))
            self.comb += [
                i.stb.eq(rl.o.stb),
                rl.o.busy.eq(~i.ack),
                i.payload.raw_bits().eq(rl.o.data),
            ]
            # TODO probes, overrides
            self.phys.append(_Phy(rl, [], []))
        self.phys_named = dict(zip(self.i_names, self.phys))
