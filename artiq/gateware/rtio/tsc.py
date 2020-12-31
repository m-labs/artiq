from migen import *

from artiq.gateware.rtio.cdc import GrayCodeTransfer


class TSC(Module):
    def __init__(self, mode, glbl_fine_ts_width=0):
        self.glbl_fine_ts_width = glbl_fine_ts_width

        # in rtio domain
        self.coarse_ts = Signal(64 - glbl_fine_ts_width)
        self.full_ts = Signal(64)
        
        # in sys domain
        # monotonic, may lag behind the counter in the IO clock domain, but
        # not be ahead of it.
        self.coarse_ts_sys = Signal.like(self.coarse_ts)
        self.full_ts_sys = Signal(64)

        # in rtio domain
        self.load = Signal()
        self.load_value = Signal.like(self.coarse_ts)

        if mode == "async":
            self.full_ts_cri = self.full_ts_sys
        elif mode == "sync":
            self.full_ts_cri = self.full_ts
        else:
            raise ValueError

        # # #

        self.sync.rtio += If(self.load,
                self.coarse_ts.eq(self.load_value)
            ).Else(
                self.coarse_ts.eq(self.coarse_ts + 1)
            )
        coarse_ts_cdc = GrayCodeTransfer(len(self.coarse_ts))  # from rtio to sys
        self.submodules += coarse_ts_cdc
        self.comb += [
            coarse_ts_cdc.i.eq(self.coarse_ts),
            self.coarse_ts_sys.eq(coarse_ts_cdc.o)
        ]

        self.comb += [
            self.full_ts.eq(self.coarse_ts << glbl_fine_ts_width),
            self.full_ts_sys.eq(self.coarse_ts_sys << glbl_fine_ts_width)
        ]
