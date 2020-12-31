from migen import *

from artiq.gateware import ad9_dds
from artiq.gateware.rtio.phy.wishbone import RT2WB


class AD9914(Module):
    def __init__(self, pads, nchannels, onehot=False, **kwargs):
        self.submodules._ll = ClockDomainsRenamer("rio_phy")(
            ad9_dds.AD9_DDS(pads, **kwargs))
        self.submodules._rt2wb = RT2WB(len(pads.a)+1, self._ll.bus, write_only=True)
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
                        If(current_address == 0x11+i,
                           ftw[i*8:(i+1)*8].eq(current_data))
                        for i in range(4)])
            elif len(pads.d) == 16:
                self.sync.rio_phy += \
                    If(selected(c), [
                        If(current_address == 0x11+2*i,
                           ftw[i*16:(i+1)*16].eq(current_data))
                        for i in range(2)])
            else:
                raise NotImplementedError

        # FTW to probe on FUD
        self.sync.rio_phy += If(current_address == 2**len(pads.a), [
            If(selected(c), probe.eq(ftw))
            for c, (probe, ftw) in enumerate(zip(self.probes, ftws))])
