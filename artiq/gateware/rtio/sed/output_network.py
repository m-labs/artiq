from migen import *

from artiq.gateware.rtio.sed import layouts


__all__ = ["latency", "OutputNetwork"]


# Based on: https://github.com/Bekbolatov/SortingNetworks/blob/master/src/main/js/gr.js
def boms_get_partner(n, l, p):
    if p == 1:
        return n ^ (1 << (l - 1))
    scale = 1 << (l - p)
    box = 1 << p
    sn = n//scale - n//scale//box*box
    if sn == 0 or sn == (box - 1):
        return n
    if (sn % 2) == 0:
        return n - scale
    return n + scale


def boms_steps_pairs(lane_count):
    d = log2_int(lane_count)
    steps = []
    for l in range(1, d+1):
        for p in range(1, l+1):
            pairs = []
            for n in range(2**d):
                partner = boms_get_partner(n, l, p)
                if partner != n:
                    if partner > n:
                        pair = (n, partner)
                    else:
                        pair = (partner, n)
                    if pair not in pairs:
                        pairs.append(pair)
            steps.append(pairs)
    return steps


def latency(lane_count):
    d = log2_int(lane_count)
    return sum(l for l in range(1, d+1))


def cmp_wrap(a, b):
    return Mux((a[-2] == a[-1]) & (b[-2] == b[-1]) & (a[-1] != b[-1]), a[-1], a < b)


class OutputNetwork(Module):
    def __init__(self, lane_count, seqn_width, layout_payload):
        self.input = [Record(layouts.output_network_node(seqn_width, layout_payload))
                      for _ in range(lane_count)]
        self.output = None

        step_input = self.input
        for step in boms_steps_pairs(lane_count):
            step_output = []
            for i in range(lane_count):
                rec = Record(layouts.output_network_node(seqn_width, layout_payload),
                             reset_less=True)
                rec.valid.reset_less = False
                step_output.append(rec)

            for node1, node2 in step:
                nondata_difference = Signal()
                for field, _ in layout_payload:
                    if field != "data":
                        f1 = getattr(step_input[node1].payload, field)
                        f2 = getattr(step_input[node2].payload, field)
                        self.comb += If(f1 != f2, nondata_difference.eq(1))

                k1 = Cat(step_input[node1].payload.channel, ~step_input[node1].valid)
                k2 = Cat(step_input[node2].payload.channel, ~step_input[node2].valid)
                self.sync += [
                    If(k1 == k2,
                        If(cmp_wrap(step_input[node1].seqn, step_input[node2].seqn),
                            step_output[node1].eq(step_input[node2]),
                            step_output[node2].eq(step_input[node1])
                        ).Else(
                            step_output[node1].eq(step_input[node1]),
                            step_output[node2].eq(step_input[node2])
                        ),
                        step_output[node1].replace_occured.eq(1),
                        step_output[node1].nondata_replace_occured.eq(nondata_difference),
                        step_output[node2].valid.eq(0),
                    ).Elif(k1 < k2,
                        step_output[node1].eq(step_input[node1]),
                        step_output[node2].eq(step_input[node2])
                    ).Else(
                        step_output[node1].eq(step_input[node2]),
                        step_output[node2].eq(step_input[node1])
                    )
                ]

            unchanged = list(range(lane_count))
            for node1, node2 in step:
                unchanged.remove(node1)
                unchanged.remove(node2)
            for node in unchanged:
                self.sync += step_output[node].eq(step_input[node])

            self.output = step_output
            step_input = step_output
