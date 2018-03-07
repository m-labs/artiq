from migen import *

from artiq.gateware.rtio.sed import layouts


__all__ = ["Gates"]


class Gates(Module):
    def __init__(self, lane_count, seqn_width, layout_fifo_payload, layout_output_network_payload):
        self.input = [Record(layouts.fifo_egress(seqn_width, layout_fifo_payload))
                      for _ in range(lane_count)]
        self.output = [Record(layouts.output_network_node(seqn_width, layout_output_network_payload),
                              reset_less=True)
                       for _ in range(lane_count)]

        if hasattr(self.output[0].payload, "fine_ts"):
            glbl_fine_ts_width = len(self.output[0].payload.fine_ts)
        else:
            glbl_fine_ts_width = 0

        self.coarse_timestamp = Signal(64-glbl_fine_ts_width)

        # # #

        for input, output in zip(self.input, self.output):
            for field, _ in output.payload.layout:
                if field == "fine_ts":
                    self.sync += output.payload.fine_ts.eq(input.payload.timestamp[:glbl_fine_ts_width])
                else:
                    self.sync += getattr(output.payload, field).eq(getattr(input.payload, field))
            self.sync += output.seqn.eq(input.seqn)
            self.comb += [
                output.replace_occured.eq(0),
                output.nondata_replace_occured.eq(0)
            ]

            self.comb += input.re.eq(input.payload.timestamp[glbl_fine_ts_width:] == self.coarse_timestamp)
            output.valid.reset_less = False
            self.sync += output.valid.eq(input.re & input.readable)
