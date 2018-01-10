import unittest

from migen import *

from artiq.gateware.rtio.sed import output_network


LANE_COUNT = 8


def simulate(input_events):
    layout_payload = [
        ("channel", 8),
        ("fine_ts", 3),
        ("address", 16),
        ("data", 512),
    ]
    dut = output_network.OutputNetwork(LANE_COUNT, LANE_COUNT*4, layout_payload)
    output = []
    def gen():
        for n, input_event in enumerate(input_events):
            yield dut.input[n].valid.eq(1)
            yield dut.input[n].seqn.eq(n)
            for k, v in input_event.items():
                yield getattr(dut.input[n].payload, k).eq(v)
        yield
        for n in range(len(input_events)):
            yield dut.input[n].valid.eq(0)
        for i in range(output_network.latency(LANE_COUNT)):
            yield
            for x in range(LANE_COUNT):
                if (yield dut.output[x].valid):
                    d = {
                        "replace_occured": (yield dut.output[x].replace_occured),
                        "channel": (yield dut.output[x].payload.channel),
                        "fine_ts": (yield dut.output[x].payload.fine_ts),
                        "address": (yield dut.output[x].payload.address),
                        "data": (yield dut.output[x].payload.data),
                    }
                    output.append(d)
    run_simulation(dut, gen())
    return output


class TestOutputNetwork(unittest.TestCase):
    def test_replace(self):
        for n_events in range(2, LANE_COUNT+1):
            with self.subTest(n_events=n_events):
                input = [{"channel": 1, "address": i} for i in range(n_events)]
                output = simulate(input)
                expect = [{'replace_occured': 1, 'channel': 1, 'fine_ts': 0, 'address': n_events-1, 'data': 0}]
                self.assertEqual(output, expect)

    def test_no_replace(self):
        for n_events in range(1, LANE_COUNT+1):
            with self.subTest(n_events=n_events):
                input = [{"channel": i, "address": i} for i in range(n_events)]
                output = simulate(input)
                expect = [{'replace_occured': 0, 'channel': i, 'fine_ts': 0, 'address': i, 'data': 0}
                          for i in range(n_events)]
                self.assertEqual(output, expect)
