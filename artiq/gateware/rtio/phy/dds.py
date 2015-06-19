from migen.fhdl.std import *

from artiq.gateware import ad9858 as ad9858_ll
from artiq.gateware.rtio.phy.wishbone import RT2WB


class AD9858(Module):
    def __init__(self, pads, nchannels=8, **kwargs):
        self.submodules._ll = RenameClockDomains(
            ad9858_ll.AD9858(pads, **kwargs), "rio")
        self.submodules._rt2wb = RT2WB(7, self._ll.bus)
        self.rtlink = self._rt2wb.rtlink
        self.probes = [Signal(32) for i in range(nchannels)]

        # # #

        # keep track of the currently selected channel
        current_channel = Signal(max=nchannels)
        self.sync.rio += If(self.rtlink.o.stb & (self.rtlink.o.address == 65),
            current_channel.eq(self.rtlink.o.data))

        # keep track of frequency tuning words, before they are FUDed
        ftws = [Signal(32) for i in range(nchannels)]
        for i in range(4):
            for c, ftw in enumerate(ftws):
                self.sync.rio += \
                    If(self.rtlink.o.stb & \
                        (self.rtlink.o.address == 0x0a+i) & \
                        (current_channel == c),
                            ftw[i*8:(i+1)*8].eq(self.rtlink.o.data)
                    )

        # FTW to probe on FUD
        for c, (probe, ftw) in enumerate(zip(self.probes, ftw)):
            fud = self.rtlink.o.stb & (self.rtlink.o.address == 64)
            self.sync.rio += If(fud & (current_channel == c), probe.eq(ftw))
