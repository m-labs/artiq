from migen import *

from artiq.gateware import ad9xxx
from artiq.gateware.rtio.phy.wishbone import RT2WB


class _AD9xxx(Module):
    def __init__(self, ftw_base, pads, nchannels, onehot=False, **kwargs):
        self.submodules._ll = ClockDomainsRenamer("rio")(
            ad9xxx.AD9xxx(pads, **kwargs))
        self.submodules._rt2wb = RT2WB(len(pads.a)+1, self._ll.bus)
        self.rtlink = self._rt2wb.rtlink
        self.probes = [Signal(32) for i in range(nchannels)]

        # # #

        # buffer the current address/data on the rtlink output
        current_address = Signal.like(self.rtlink.o.address)
        current_data = Signal.like(self.rtlink.o.data)
        self.sync.rio += If(self.rtlink.o.stb,
                            current_address.eq(self.rtlink.o.address),
                            current_data.eq(self.rtlink.o.data))

        # keep track of the currently selected channel(s)
        current_sel = Signal(len(current_data)-1)
        self.sync.rio += If(current_address == 2**len(pads.a) + 1,
                            current_sel.eq(current_data[1:]))  # strip reset

        def selected(c):
            if onehot:
                return current_sel[c]
            else:
                return current_sel == c

        # keep track of frequency tuning words, before they are FUDed
        ftws = [Signal(32) for i in range(nchannels)]
        for c, ftw in enumerate(ftws):
            if len(pads.d) == 8:
                self.sync.rio_phy += \
                    If(selected(c), [
                        If(current_address == ftw_base+i,
                           ftw[i*8:(i+1)*8].eq(current_data))
                        for i in range(4)])
            elif len(pads.d) == 16:
                self.sync.rio_phy += \
                    If(selected(c), [
                        If(current_address == ftw_base+2*i,
                           ftw[i*16:(i+1)*16].eq(current_data))
                        for i in range(2)])
            else:
                raise NotImplementedError

        # FTW to probe on FUD
        self.sync.rio_phy += If(current_address == 2**len(pads.a), [
            If(selected(c), probe.eq(ftw))
            for c, (probe, ftw) in enumerate(zip(self.probes, ftws))])


class AD9858(_AD9xxx):
    def __init__(self, *args, **kwargs):
        _AD9xxx.__init__(self, 0x0a, *args, **kwargs)


class AD9914(_AD9xxx):
    def __init__(self, *args, **kwargs):
        _AD9xxx.__init__(self, 0x2d, *args, **kwargs)
