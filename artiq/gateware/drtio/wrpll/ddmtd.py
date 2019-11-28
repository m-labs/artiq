from migen import *
from migen.genlib.cdc import PulseSynchronizer, MultiReg
from misoc.interconnect.csr import *


class DDMTDEdgeDetector(Module):
    def __init__(self, i):
        self.rising = Signal()

        history = Signal(4)
        deglitched = Signal()
        self.sync.helper += history.eq(Cat(history[1:], i))
        self.comb += deglitched.eq(i | history[0] | history[1] | history[2] | history[3])

        deglitched_r = Signal()
        self.sync.helper += [
            deglitched_r.eq(deglitched),
            self.rising.eq(deglitched & ~deglitched_r)
        ]


class DDMTD(Module, AutoCSR):
    def __init__(self, N, i):
        self.arm = CSR()
        self.tag = CSRStatus(N)

        # in helper clock domain
        self.h_tag = Signal(N)
        self.h_tag_update = Signal()

        # # #

        ed = DDMTDEdgeDetector(i)
        self.submodules += ed

        counter = Signal(N)
        self.sync.helper += [
            counter.eq(counter + 1),
            self.h_tag_update.eq(0),
            If(ed.rising,
                self.h_tag_update.eq(1),
                self.h_tag.eq(counter)
            )
        ]

        tag_update_ps = PulseSynchronizer("helper", "sys")
        self.submodules += tag_update_ps
        self.comb += tag_update_ps.i.eq(self.h_tag_update)
        tag_update = Signal()
        self.sync += tag_update.eq(tag_update_ps.o)

        tag = Signal(N)
        self.h_tag.attr.add("no_retiming")
        self.specials += MultiReg(self.h_tag, tag)

        self.sync += [
            If(self.arm.re & self.arm.r, self.arm.w.eq(1)),
            If(tag_update,
                If(self.arm.w, self.tag.status.eq(tag)),
                self.arm.w.eq(0),
            )
        ]
