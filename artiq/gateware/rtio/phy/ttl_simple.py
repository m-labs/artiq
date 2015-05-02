from migen.fhdl.std import *
from migen.genlib.cdc import MultiReg

from artiq.gateware.rtio import rtlink


class Output(Module):
    def __init__(self, pad):
        self.rtlink = rtlink.Interface(rtlink.OInterface(1))

        # # #

        self.sync.rio_phy += If(self.rtlink.o.stb, pad.eq(self.rtlink.o.data))


class Inout(Module):
    def __init__(self, pad):
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(2, 2),
            rtlink.IInterface(1))

        # # #
        
        ts = TSTriple()
        self.specials += ts.get_tristate(pad)
        sensitivity = Signal(2)

        self.sync.rio_phy += If(self.rtlink.o.stb,
            Case(self.rtlink.o.address, {
                0: ts.o.eq(self.rtlink.o.data[0]),
                1: ts.oe.eq(self.rtlink.o.data[0]),
                2: sensitivity.eq(self.rtlink.o.data)
            }).makedefault()
        )
        
        i = Signal()
        i_d = Signal()
        self.specials += MultiReg(ts.i, i, "rio_phy")
        self.sync.rio_phy += i_d.eq(i)
        self.comb += [
            self.rtlink.i.stb.eq(
                (sensitivity[0] & ( i & ~i_d)) |
                (sensitivity[1] & (~i &  i_d))
            ),
            self.rtlink.i.data.eq(i)
        ]
