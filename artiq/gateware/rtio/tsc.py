from migen import *

class TSC(Module):
    def __init__(self, glbl_fine_ts_width=0):
        self.glbl_fine_ts_width = glbl_fine_ts_width

        # in rtio domain
        self.coarse_ts = Signal(64 - glbl_fine_ts_width)
        self.full_ts = Signal(64)
        
        self.load = Signal()
        self.load_value = Signal.like(self.coarse_ts)

        self.full_ts_cri = self.full_ts

        # # #

        self.sync += If(self.load,
                self.coarse_ts.eq(self.load_value)
            ).Else(
                self.coarse_ts.eq(self.coarse_ts + 1)
            )

        self.comb += [
            self.full_ts.eq(self.coarse_ts << glbl_fine_ts_width),
        ]
