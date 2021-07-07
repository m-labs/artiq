from migen import *
from migen.genlib.cdc import MultiReg
from migen.genlib.io import DifferentialInput, DifferentialOutput

from artiq.gateware.rtio import rtlink


class Output(Module):
    def __init__(self, pad, pad_n=None):
        self.rtlink = rtlink.Interface(rtlink.OInterface(1))
        pad_o = Signal(reset_less=True)
        self.probes = [pad_o]
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
                pad_o.eq(override_o)
            ).Else(
                pad_o.eq(pad_k)
            )
        ]
        if pad_n is None:
            self.comb += pad.eq(pad_o)
        else:
            self.specials += DifferentialOutput(pad_o, pad, pad_n)


class Input(Module):
    def __init__(self, pad, pad_n=None):
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(2, 2),
            rtlink.IInterface(1))
        self.overrides = []
        self.probes = []

        #: Registered copy of the input state, in the rio_phy clock domain.
        self.input_state = Signal()

        # # #

        sensitivity = Signal(2)

        sample = Signal()
        self.sync.rio += [
            sample.eq(0),
            If(self.rtlink.o.stb & self.rtlink.o.address[1],
                sensitivity.eq(self.rtlink.o.data),
                If(self.rtlink.o.address[0], sample.eq(1))
            )
        ]

        i = Signal()
        i_d = Signal(reset_less=True)
        pad_i = Signal()
        if pad_n is None:
            self.comb += pad_i.eq(pad)
        else:
            self.specials += DifferentialInput(pad, pad_n, pad_i)
        self.specials += MultiReg(pad_i, i, "rio_phy")
        self.sync.rio_phy += i_d.eq(i)
        self.comb += [
            self.rtlink.i.stb.eq(
                sample |
                (sensitivity[0] & ( i & ~i_d)) |
                (sensitivity[1] & (~i &  i_d))
            ),
            self.rtlink.i.data.eq(i),
            self.input_state.eq(i)
        ]

        self.probes += [i]


class InOut(Module):
    def __init__(self, pad):
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(2, 2),
            rtlink.IInterface(1))
        override_en = Signal()
        override_o = Signal()
        override_oe = Signal()
        self.overrides = [override_en, override_o, override_oe]
        self.probes = []

        # Output enable, for interfacing to external buffers.
        self.oe = Signal()
        # Registered copy of the input state, in the rio_phy clock domain.
        self.input_state = Signal()

        # # #
        
        ts = TSTriple()
        self.specials += ts.get_tristate(pad)
        sensitivity = Signal(2)

        o_k = Signal()
        oe_k = Signal()
        self.oe.attr.add("no_retiming")
        self.sync.rio_phy += [
            If(self.rtlink.o.stb,
                If(self.rtlink.o.address == 0, o_k.eq(self.rtlink.o.data[0])),
                If(self.rtlink.o.address == 1, oe_k.eq(self.rtlink.o.data[0])),
            ),
            If(override_en,
                ts.o.eq(override_o),
                self.oe.eq(override_oe)
            ).Else(
                ts.o.eq(o_k),
                self.oe.eq(oe_k)
            )
        ]
        self.comb += ts.oe.eq(self.oe)
        sample = Signal()
        self.sync.rio += [
            sample.eq(0),
            If(self.rtlink.o.stb & self.rtlink.o.address[1],
                sensitivity.eq(self.rtlink.o.data),
                If(self.rtlink.o.address[0], sample.eq(1))
            )
        ]
        
        i = Signal()
        i_d = Signal()
        self.specials += MultiReg(ts.i, i, "rio_phy")
        self.sync.rio_phy += i_d.eq(i)
        self.comb += [
            self.rtlink.i.stb.eq(
                sample |
                (sensitivity[0] & ( i & ~i_d)) |
                (sensitivity[1] & (~i &  i_d))
            ),
            self.rtlink.i.data.eq(i),
            self.input_state.eq(i)
        ]

        self.probes += [i, ts.oe]


class ClockGen(Module):
    def __init__(self, pad, ftw_width=24):
        self.rtlink = rtlink.Interface(rtlink.OInterface(ftw_width))

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
