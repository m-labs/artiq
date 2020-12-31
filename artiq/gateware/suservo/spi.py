import logging
from collections import namedtuple

from migen import *
from migen.genlib.fsm import FSM, NextState
from migen.genlib import io


logger = logging.getLogger(__name__)


# all times in cycles
SPIParams = namedtuple("SPIParams", [
    "channels", # number of MOSI? data lanes
    "width",    # transfer width
    "clk",      # CLK half cycle width (in cycles)
])


class SPISimple(Module):
    """Simple reduced SPI interface.

    * Multiple MOSI lines
    * Supports differential CLK/CS_N/MOSI
    * Fixed CLK timing
    * SPI MODE 0 (CPHA=0, CPOL=0)
    """
    def __init__(self, pads, params):
        self.params = p = params
        self.data = [Signal(p.width, reset_less=True)
                for i in range(p.channels)]  # data to be output, MSB first
        self.start = Signal()  # start transfer
        self.done = Signal()   # transfer complete, next transfer can be
                               # started

        ###

        assert p.clk >= 1

        cnt = Signal(max=max(2, p.clk), reset_less=True)
        cnt_done = Signal()
        cnt_next = Signal()
        self.comb += cnt_done.eq(cnt == 0)
        self.sync += [
                If(cnt_done,
                    If(cnt_next,
                        cnt.eq(p.clk - 1)
                    )
                ).Else(
                    cnt.eq(cnt - 1)
                )
        ]

        for i, d in enumerate(self.data):
            self.comb += getattr(pads, "mosi{}".format(i)).eq(d[-1])

        bits = Signal(max=p.width + 1, reset_less=True)

        self.submodules.fsm = fsm = CEInserter()(FSM("IDLE"))

        self.comb += fsm.ce.eq(cnt_done)

        fsm.act("IDLE",
                self.done.eq(1),
                pads.cs_n.eq(1),
                If(self.start,
                    cnt_next.eq(1),
                    NextState("SETUP")
                )
        )
        fsm.act("SETUP",
                cnt_next.eq(1),
                If(bits == 0,
                    NextState("IDLE")
                ).Else(
                    NextState("HOLD")
                )
        )
        fsm.act("HOLD",
                cnt_next.eq(1),
                pads.clk.eq(1),
                NextState("SETUP")
        )

        self.sync += [
            If(fsm.ce,
                If(fsm.before_leaving("HOLD"),
                    bits.eq(bits - 1),
                    [d[1:].eq(d) for d in self.data]
                ),
                If(fsm.ongoing("IDLE"),
                    bits.eq(p.width)
                )
            )
        ]
