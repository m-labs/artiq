from migen import *
from migen.genlib.cdc import MultiReg
from misoc.interconnect.csr import *


class FrequencyCounter(Module, AutoCSR):
    def __init__(self, width=8):
        self.freq_count = CSRStatus(width)

        # # #

        toggle = Signal(reset_less=True)
        toggle_sys = Signal()
        toggle.attr.add("no_retiming")
        self.sync.cl += toggle.eq(~toggle)
        self.specials += MultiReg(toggle, toggle_sys)

        timer = Signal(width+1)
        tick = Signal(reset=1)
        count = Signal(width)
        toggle_sys_r = Signal()
        self.sync += [
            Cat(timer, tick).eq(timer + 1),
            toggle_sys_r.eq(toggle_sys),
            If(tick,
                self.freq_count.status.eq(count),
                count.eq(0)
            ).Else(
                If(toggle_sys & ~toggle_sys_r, count.eq(count + 1))
            )
        ]


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
    def __init__(self, width):
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
            pix.stb.eq(dval & fval & lval),
            pix.eop.eq(~fval & last_fval),
            Cat(pix.a, pix.b, pix.c).eq(Cat(cl[i] for i in bitseq))
        ]
        self.sync.cl += [
            last_lval.eq(lval),
            last_fval.eq(fval),
            If(dval,
                pix.x.eq(pix.x + 1),
            ),
            If(~lval,
                If(last_lval,
                    last_x.eq(pix.x),
                    pix.y.eq(pix.y + 1)
                ),
                pix.x.eq(0)
            ),
            If(~fval,
                If(last_fval,
                    last_y.eq(pix.y)
                ),
                pix.y.eq(0)
            )
        ]

        last_x.attr.add("no_retiming")
        last_y.attr.add("no_retiming")
        self.specials += [
            MultiReg(last_x, self.last_x.status),
            MultiReg(last_y, self.last_y.status)
        ]


class ROI(Module):
    """ROI Engine. For each frame, accumulates pixels values within a
    rectangular region of interest, and reports the total."""

    @staticmethod
    def count_len(width, shift):
        # limit width to 31 to avoid problems with CPUs and RTIO inputs
        return min(31, 2*width + 16 - shift)

    def __init__(self, pix, shift):
        count_len = ROI.count_len(len(pix.x), shift)

        self.cfg = cfg = Record([
            ("x0", len(pix.x)),
            ("x1", len(pix.x)),
            ("y0", len(pix.y)),
            ("y1", len(pix.y)),
        ])
        self.out = out = Record([
            ("update", 1),
            # registered output - can be used as CDC input
            ("count", count_len),
        ])

        # # #

        # stage 1 - generate "good" (in-ROI) signals
        y_good = Signal()
        x_good = Signal()
        stb = Signal()
        eop = Signal()
        gray = Signal(16)
        self.sync.cl += [
            If(pix.y == cfg.y0,
                y_good.eq(1)
            ),
            If(pix.y == cfg.y1,
                y_good.eq(0)
            ),
            If(pix.x == cfg.x0,
                x_good.eq(1)
            ),
            If(pix.x == cfg.x1,
                x_good.eq(0)
            ),
            If(pix.eop,
                y_good.eq(0),
                x_good.eq(0)
            ),
            gray.eq(Cat(pix.a, pix.b)[shift:]),
            stb.eq(pix.stb),
            eop.eq(pix.eop)
        ]

        # stage 2 - accumulate
        count = Signal(count_len)
        self.sync.cl += [
            If(stb & x_good & y_good,
                count.eq(count + gray),
            ),

            out.update.eq(0),
            If(eop,
                count.eq(0),
                out.update.eq(1),
                out.count.eq(count)
            )
        ]
