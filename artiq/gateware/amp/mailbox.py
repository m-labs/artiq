from migen import *
from misoc.interconnect import wishbone


class Mailbox(Module):
    def __init__(self):
        self.i1 = wishbone.Interface()
        self.i2 = wishbone.Interface()

        # # #

        value = Signal(32)
        for i in self.i1, self.i2:
            self.sync += [
                i.dat_r.eq(value),
                i.ack.eq(0),
                If(i.cyc & i.stb & ~i.ack,
                    i.ack.eq(1),
                    If(i.we, value.eq(i.dat_w))
                )
            ]
