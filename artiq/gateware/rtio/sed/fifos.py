from operator import or_
from functools import reduce

from migen import *
from migen.genlib.fifo import SyncFIFOBuffered

from artiq.gateware.rtio.sed import layouts


__all__ = ["FIFOs"]


class FIFOs(Module):
    def __init__(self, lane_count, fifo_depth, high_watermark, layout_payload, report_buffer_space=False):
        seqn_width = layouts.seqn_width(lane_count, fifo_depth)
        self.input = [Record(layouts.fifo_ingress(seqn_width, layout_payload))
                      for _ in range(lane_count)]
        self.output = [Record(layouts.fifo_egress(seqn_width, layout_payload))
                       for _ in range(lane_count)]

        if report_buffer_space:
            self.buffer_space = Signal(max=fifo_depth+1)

        # # #

        fifos = []
        for input, output in zip(self.input, self.output):
            fifo = SyncFIFOBuffered(seqn_width + layout_len(layout_payload), fifo_depth)
            self.submodules += fifo
            fifos.append(fifo)

            self.comb += [
                fifo.din.eq(Cat(input.seqn, input.payload.raw_bits())),
                fifo.we.eq(input.we),
                input.writable.eq(fifo.writable),
                input.high_watermark.eq(fifo.level >= high_watermark),

                Cat(output.seqn, output.payload.raw_bits()).eq(fifo.dout),
                output.readable.eq(fifo.readable),
                fifo.re.eq(output.re)
            ]

        if report_buffer_space:
            def compute_max(elts):
                l = len(elts)
                if l == 1:
                    return elts[0], 0
                else:
                    maximum1, latency1 = compute_max(elts[:l//2])
                    maximum2, latency2 = compute_max(elts[l//2:])
                    maximum = Signal(max(len(maximum1), len(maximum2)))
                    self.sync += [
                        If(maximum1 > maximum2,
                            maximum.eq(maximum1)
                        ).Else(
                            maximum.eq(maximum2)
                        )
                    ]
                    latency = max(latency1, latency2) + 1
                    return maximum, latency

            max_level, latency = compute_max([fifo.level for fifo in fifos])
            max_level_valid = Signal()
            max_level_valid_counter = Signal(max=latency)
            self.sync += [
                If(reduce(or_, [fifo.we for fifo in fifos]),
                    max_level_valid.eq(0),
                    max_level_valid_counter.eq(latency - 1)
                ).Elif(max_level_valid_counter == 0,
                    max_level_valid.eq(1)
                ).Else(
                    max_level_valid_counter.eq(max_level_valid_counter - 1)
                )
            ]
            self.comb += If(max_level_valid, self.buffer_space.eq(fifo_depth - max_level))
