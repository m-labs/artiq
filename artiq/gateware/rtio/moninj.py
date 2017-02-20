from migen import *
from migen.genlib.cdc import BusSynchronizer, MultiReg
from misoc.interconnect.csr import *


class Monitor(Module, AutoCSR):
    def __init__(self, channels):
        chan_probes = [c.probes for c in channels]

        max_chan_probes = max(len(cp) for cp in chan_probes)
        max_probe_len = max(len(p) for cp in chan_probes for p in cp)
        self.chan_sel = CSRStorage(bits_for(len(chan_probes)-1))
        self.probe_sel = CSRStorage(bits_for(max_chan_probes-1))
        self.value_update = CSR()
        self.value = CSRStatus(max_probe_len)

        # # #

        chan_probes_sys = []
        for cp in chan_probes:
            cp_sys = []
            for p in cp:
                vs = BusSynchronizer(len(p), "rio", "sys")
                self.submodules += vs
                self.comb += vs.i.eq(p)
                cp_sys.append(vs.o)
            cp_sys += [0]*(max_chan_probes-len(cp))
            chan_probes_sys.append(Array(cp_sys)[self.probe_sel.storage])
        self.sync += If(self.value_update.re,
            self.value.status.eq(
                Array(chan_probes_sys)[self.chan_sel.storage]))


class Injector(Module, AutoCSR):
    def __init__(self, channels):
        chan_overrides = [c.overrides for c in channels]

        max_chan_overrides = max(len(co) for co in chan_overrides)
        max_override_len = max(len(o) for co in chan_overrides for o in co)
        self.chan_sel = CSRStorage(bits_for(len(chan_overrides)-1))
        self.override_sel = CSRStorage(bits_for(max_chan_overrides-1))
        self.value = CSR(max_override_len)

        # # #

        chan_overrides_sys = []
        for n_channel, co in enumerate(chan_overrides):
            co_sys = []
            for n_override, o in enumerate(co):
                # We do the clock domain transfer with a simple double-latch.
                # Software has to ensure proper timing of any strobe signal etc.
                # to avoid problematic glitches.
                o_sys = Signal.like(o)
                self.specials += MultiReg(o_sys, o, "rio")
                self.sync += If(self.value.re & (self.chan_sel.storage == n_channel)
                                & (self.override_sel.storage == n_override),
                                    o_sys.eq(self.value.r))
                co_sys.append(o_sys)
            co_sys += [0]*(max_chan_overrides-len(co))
            chan_overrides_sys.append(Array(co_sys)[self.override_sel.storage])
        self.comb += self.value.w.eq(
            Array(chan_overrides_sys)[self.chan_sel.storage])


class MonInj(Module, AutoCSR):
    def __init__(self, channels):
        self.submodules.mon = Monitor(channels)
        self.submodules.inj = Injector(channels)
