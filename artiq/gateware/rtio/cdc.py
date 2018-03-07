from migen import *
from migen.genlib.cdc import *


__all__ = ["GrayCodeTransfer", "BlindTransfer"]


# note: transfer is in rtio/sys domains and not affected by the reset CSRs
class GrayCodeTransfer(Module):
    def __init__(self, width):
        self.i = Signal(width)  # in rtio domain
        self.o = Signal(width, reset_less=True)  # in sys domain

        # # #

        # convert to Gray code
        value_gray_rtio = Signal(width, reset_less=True)
        self.sync.rtio += value_gray_rtio.eq(self.i ^ self.i[1:])
        # transfer to system clock domain
        value_gray_sys = Signal(width)
        value_gray_rtio.attr.add("no_retiming")
        self.specials += MultiReg(value_gray_rtio, value_gray_sys)
        # convert back to binary
        value_sys = Signal(width)
        self.comb += value_sys[-1].eq(value_gray_sys[-1])
        for i in reversed(range(width-1)):
            self.comb += value_sys[i].eq(value_sys[i+1] ^ value_gray_sys[i])
        self.sync += self.o.eq(value_sys)


class BlindTransfer(Module):
    def __init__(self, idomain="rio", odomain="rsys", data_width=0):
        self.i = Signal()
        self.o = Signal()
        if data_width:
            self.data_i = Signal(data_width)
            self.data_o = Signal(data_width, reset_less=True)

        # # #

        ps = PulseSynchronizer(idomain, odomain)
        ps_ack = PulseSynchronizer(odomain, idomain)
        self.submodules += ps, ps_ack
        blind = Signal()
        isync = getattr(self.sync, idomain)
        isync += [
            If(self.i, blind.eq(1)),
            If(ps_ack.o, blind.eq(0))
        ]
        self.comb += [
            ps.i.eq(self.i & ~blind),
            ps_ack.i.eq(ps.o),
            self.o.eq(ps.o)
        ]

        if data_width:
            bxfer_data = Signal(data_width, reset_less=True)
            isync += If(ps.i, bxfer_data.eq(self.data_i))
            bxfer_data.attr.add("no_retiming")
            self.specials += MultiReg(bxfer_data, self.data_o,
                                      odomain=odomain)
