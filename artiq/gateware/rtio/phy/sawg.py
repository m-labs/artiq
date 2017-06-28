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
        cfg = self.i[0]
        rl = rtlink.Interface(rtlink.OInterface(
            data_width=len(cfg.data), address_width=len(cfg.addr),
            enable_replace=False))
        self.comb += [
            cfg.stb.eq(rl.o.stb),
            rl.o.busy.eq(~cfg.ack),
            cfg.data.eq(rl.o.data),
            cfg.addr.eq(rl.o.address),
        ]
        self.phys.append(_Phy(rl, [], []))
        for i in self.i[1:]:
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
