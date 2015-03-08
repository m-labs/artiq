from migen.fhdl.std import *
from migen.genlib.cdc import MultiReg

from artiq.gateware.rtio.rbus import create_rbus


class SimplePHY(Module):
    def __init__(self, pads, output_only_pads=set()):
        self.rbus = create_rbus(0, pads, output_only_pads)
        self.loopback_latency = 3

        # # #

        for pad, chif in zip(pads, self.rbus):
            o_pad = Signal()
            self.sync.rio += If(chif.o_stb, o_pad.eq(chif.o_value))
            if hasattr(chif, "oe"):
                ts = TSTriple()
                i_pad = Signal()
                self.sync.rio += ts.oe.eq(chif.oe)
                self.comb += ts.o.eq(o_pad)
                self.specials += MultiReg(ts.i, i_pad, "rio"), \
                    ts.get_tristate(pad)

                i_pad_d = Signal()
                self.sync.rio += i_pad_d.eq(i_pad)
                self.comb += chif.i_stb.eq(i_pad ^ i_pad_d), \
                    chif.i_value.eq(i_pad)
            else:
                self.comb += pad.eq(o_pad)
