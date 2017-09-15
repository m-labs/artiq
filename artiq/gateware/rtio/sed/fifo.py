from migen import *
from migen.genlib.fifo import *

from artiq.gateware.rtio.sed import layouts


__all__ = ["FIFO"]


class FIFO(Module):
    def __init__(self, lane_count, mode, fifo_depth, layout_payload):
        seqn_width = layouts.seqn_width(lane_count, fifo_width)
        self.input = [layouts.fifo_ingress(seqn_width, layout_payload)
                      for _ in range(lane_count)]
        self.output = [layouts.fifo_egress(seqn_width, layout_payload)
                       for _ in range(lane_count)]

        if mode == "sync":
            fifo_cls = fifo.SyncFIFOBuffered
        elif mode == "async":
            fifo_cls = fifo.AsyncFIFO
        else:
            raise ValueError

        for input, output in zip(self.input, self.output):
            fifo = fifo_cls(layout_len(layout_payload), fifo_depth)
            self.submodules += fifo

            self.comb += [
                fifo.din.eq(input.payload.raw_bits()),
                fifo.we.eq(input.we),
                input.writable.eq(fifo.writable),

                output.payload.raw_bits().eq(fifo.dout),
                output.readable.eq(fifo.readable),
                fifo.re.eq(output.re)
            ]
