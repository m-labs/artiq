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

        # buffer the current address/data on the rtlink output
        current_address = Signal.like(self.rtlink.o.address)
        current_data = Signal.like(self.rtlink.o.data)
        self.sync.rio += If(self.rtlink.o.stb,
                            current_address.eq(self.rtlink.o.address),
                            current_data.eq(self.rtlink.o.data))

        # keep track of the currently selected channel
        current_channel = Signal(max=nchannels)
        self.sync.rio += If(current_address == 2**flen(pads.a) + 1,
                            current_channel.eq(current_data))

        # keep track of frequency tuning words, before they are FUDed
        ftws = [Signal(32) for i in range(nchannels)]
        for c, ftw in enumerate(ftws):
            if flen(pads.d) == 8:
                self.sync.rio += \
                    If(current_channel == c, [
                        If(current_address == ftw_base+i,
                           ftw[i*8:(i+1)*8].eq(current_data))
                        for i in range(4)])
            elif flen(pads.d) == 16:
                self.sync.rio += \
                    If(current_channel == c, [
                        If(current_address == ftw_base+2*i,
                           ftw[i*16:(i+1)*16].eq(current_data))
                        for i in range(2)])
            else:
                raise NotImplementedError

        # FTW to probe on FUD
        self.sync.rio += If(current_address == 2**flen(pads.a), [
            If(current_channel == c, probe.eq(ftw))
            for c, (probe, ftw) in enumerate(zip(self.probes, ftws))])


class AD9858(_AD9xxx):
    def __init__(self, pads, nchannels, **kwargs):
        _AD9xxx.__init__(self, 0x0a, pads, nchannels, **kwargs)


class AD9914(_AD9xxx):
    def __init__(self, pads, nchannels, **kwargs):
        _AD9xxx.__init__(self, 0x2d, pads, nchannels, **kwargs)
