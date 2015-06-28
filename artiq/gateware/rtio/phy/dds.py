from migen.fhdl.std import *

from artiq.gateware import ad9xxx
from artiq.gateware.rtio.phy.wishbone import RT2WB


class _AD9xxx(Module):
    def __init__(self, ftw_base, pads, nchannels, **kwargs):
        self.submodules._ll = RenameClockDomains(
            ad9xxx.AD9xxx(pads, **kwargs), "rio")
        self.submodules._rt2wb = RT2WB(flen(pads.a)+1, self._ll.bus)
        self.rtlink = self._rt2wb.rtlink
        self.probes = [Signal(32) for i in range(nchannels)]

        # # #

        # keep track of the currently selected channel
        current_channel = Signal(max=nchannels)
        self.sync.rio += If(self.rtlink.o.stb & 
            (self.rtlink.o.address == 2**flen(pads.a)+1),
                current_channel.eq(self.rtlink.o.data))

        # keep track of frequency tuning words, before they are FUDed
        ftws = [Signal(32) for i in range(nchannels)]
        for c, ftw in enumerate(ftws):
            if flen(pads.d) == 8:
                for i in range(4):
                    self.sync.rio += \
                        If(self.rtlink.o.stb & \
                            (self.rtlink.o.address == ftw_base+i) & \
                            (current_channel == c),
                                ftw[i*8:(i+1)*8].eq(self.rtlink.o.data)
                        )
            elif flen(pads.d) == 16:
                for i in range(2):
                    self.sync.rio += \
                        If(self.rtlink.o.stb & \
                            (self.rtlink.o.address == ftw_base+2*i) & \
                            (current_channel == c),
                                ftw[i*16:(i+1)*16].eq(self.rtlink.o.data)
                        )
            else:
                raise NotImplementedError

        # FTW to probe on FUD
        for c, (probe, ftw) in enumerate(zip(self.probes, ftws)):
            fud = self.rtlink.o.stb & \
                (self.rtlink.o.address == 2**flen(pads.a))
            self.sync.rio += If(fud & (current_channel == c), probe.eq(ftw))


class AD9858(_AD9xxx):
    def __init__(self, pads, nchannels, **kwargs):
        _AD9xxx.__init__(self, 0x0a, pads, nchannels, **kwargs)


class AD9914(_AD9xxx):
    def __init__(self, pads, nchannels, **kwargs):
        _AD9xxx.__init__(self, 0x2d, pads, nchannels, **kwargs)
