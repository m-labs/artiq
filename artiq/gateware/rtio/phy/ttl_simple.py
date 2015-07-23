from migen.fhdl.std import *
from migen.genlib.cdc import MultiReg

from artiq.gateware.rtio import rtlink


class Output(Module):
    def __init__(self, pad):
        self.rtlink = rtlink.Interface(rtlink.OInterface(1))
        self.probes = [pad]
        override_en = Signal()
        override_o = Signal()
        self.overrides = [override_en, override_o]

        # # #

        pad_k = Signal()
        self.sync.rio_phy += [
            If(self.rtlink.o.stb,
                pad_k.eq(self.rtlink.o.data)
            ),
            If(override_en,
                pad.eq(override_o)
            ).Else(
                pad.eq(pad_k)
            )
        ]


class Inout(Module):
    def __init__(self, pad):
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(2, 2),
            rtlink.IInterface(1))
        override_en = Signal()
        override_o = Signal()
        override_oe = Signal()
        self.overrides = [override_en, override_o, override_oe]
        self.probes = []

        # # #
        
        ts = TSTriple()
        self.specials += ts.get_tristate(pad)
        sensitivity = Signal(2)

        o_k = Signal()
        oe_k = Signal()
        self.sync.rio_phy += [
            If(self.rtlink.o.stb,
                If(self.rtlink.o.address == 0, o_k.eq(self.rtlink.o.data[0])),
                If(self.rtlink.o.address == 1, oe_k.eq(self.rtlink.o.data[0])),
            ),
            If(override_en,
                ts.o.eq(override_o),
                ts.oe.eq(override_oe)
            ).Else(
                ts.o.eq(o_k),
                ts.oe.eq(oe_k)
            )
        ]
        self.sync.rio += If(self.rtlink.o.stb & (self.rtlink.o.address == 2),
            sensitivity.eq(self.rtlink.o.data))
        
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

        self.probes += [i, ts.oe]


class ClockGen(Module):
    def __init__(self, pad, ftw_width=24):
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(ftw_width, suppress_nop=False))

        # # #

        ftw = Signal(ftw_width)
        acc = Signal(ftw_width)
        self.sync.rio += If(self.rtlink.o.stb, ftw.eq(self.rtlink.o.data))
        self.sync.rio_phy += [
            acc.eq(acc + ftw),
            # rtlink takes precedence over regular acc increments
            If(self.rtlink.o.stb,
                If(self.rtlink.o.data != 0,
                    # known phase on frequency write: at rising edge
                    acc.eq(2**(ftw_width - 1))
                ).Else(
                    # set output to 0 on stop
                    acc.eq(0)
                )
            ),
            pad.eq(acc[-1])
        ]
