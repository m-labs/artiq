from migen import *
from migen.genlib.cdc import MultiReg
from misoc.interconnect.csr import *


bitseq = [
    #  0   1   2   3   4   5   6
       6,  5,  4,  3,  2,  1, 27,

    #  7   8   9  10  11  12  13
      26,  0, 13, 12, 11, 10,  9,

    # 14  15  16  17  18  19  20
      25, 24,  8,  7, 20, 19, 18,

    # 21  22  23
      17, 23, 22
]

assert len(set(bitseq)) == 24


class Parser(Module, AutoCSR):
    """Parses 28 bit encoded words and track pixel coordinates."""
    def __init__(self, width=12):
        self.cl = cl = Signal(28)

        self.last_x = CSRStatus(width)
        self.last_y = CSRStatus(width)

        self.pix = pix = Record([
            ("x", width),
            ("y", width),
            ("a", 8),
            ("b", 8),
            ("c", 8),
            ("stb", 1),
            ("eop", 1),
        ])

        # # #

        last_x = Signal(width)
        last_y = Signal(width)

        lval = Signal()
        fval = Signal()
        dval = Signal()
        last_lval = Signal()
        last_fval = Signal()
        self.comb += [
            Cat(dval, fval, lval).eq(cl[14:17]),
            pix.stb.eq(dval),
            pix.eop.eq(~fval & last_fval),
            Cat(pix.a, pix.b, pix.c).eq(Cat(cl[i] for i in bitseq))
        ]
        self.sync.cl += [
            last_lval.eq(lval),
            last_fval.eq(fval),
            pix.x.eq(pix.x + 1),
            If(~lval,
                pix.x.eq(0),
                If(last_lval, last_x.eq(pix.x)),
                If(last_fval & last_lval,
                    pix.y.eq(pix.y + 1)
                )
            ),
            If(~fval,
                If(last_fval, last_y.eq(pix.y)),
                pix.y.eq(0)
            )
        ]

        last_x.attr.add("no_retiming")
        last_y.attr.add("no_retiming")
        self.specials += [
            MultiReg(last_x, self.last_x.status),
            MultiReg(last_y, self.last_y.status)
        ]
