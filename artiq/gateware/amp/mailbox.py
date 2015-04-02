from migen.fhdl.std import *
from migen.bus import wishbone


class Mailbox(Module):
    def __init__(self):
        self.i1 = wishbone.Interface()
        self.i2 = wishbone.Interface()

        # # #

        value = Signal(32)
        for i in self.i1, self.i2:
            self.sync += [
                i.ack.eq(0),
                If(i.cyc & i.stb & ~i.ack, i.ack.eq(1)),

                i.dat_r.eq(value),
                If(i.cyc & i.stb & i.we,
                   [If(i.sel[j], value[j*8:j*8+8].eq(i.dat_w[j*8:j*8+8]))
                    for j in range(4)]
                )
            ]
