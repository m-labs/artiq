from migen.fhdl.std import *
from migen.bank.description import *
from migen.genlib.cdc import BusSynchronizer

class Monitor(Module, AutoCSR):
    def __init__(self, channels):
        chan_probes = [c.probes for c in channels]

        max_chan_probes = max(len(cp) for cp in chan_probes)
        max_probe_len = max(flen(p) for cp in chan_probes for p in cp)
        self.chan_sel = CSRStorage(bits_for(len(chan_probes)-1))
        self.probe_sel = CSRStorage(bits_for(max_chan_probes-1))
        self.probe_value = CSRStatus(max_probe_len)

        # # #

        chan_probes_sys = []
        for cp in chan_probes:
            cp_sys = []
            for p in cp:
                vs = BusSynchronizer(flen(p), "rio", "rsys")
                self.submodules += vs
                self.comb += vs.i.eq(p)
                cp_sys.append(vs.o)
            cp_sys += [0]*(max_chan_probes-len(cp))
            chan_probes_sys.append(Array(cp_sys)[self.probe_sel.storage])
        self.comb += self.probe_value.status.eq(
            Array(chan_probes_sys)[self.chan_sel.storage])
