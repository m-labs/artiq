import unittest

from migen import *

from artiq.gateware import rtio
from artiq.gateware.rtio.sed import output_network, output_driver
from artiq.gateware.rtio.phy import ttl_simple
from artiq.gateware.rtio import rtlink


LANE_COUNT = 8


class BusyPHY(Module):
    def __init__(self):
        self.rtlink = rtlink.Interface(rtlink.OInterface(1))
        self.comb += self.rtlink.o.busy.eq(1)


class DUT(Module):
    def __init__(self):
        self.ttl0 = Signal()
        self.ttl1 = Signal()
        self.ttl2 = Signal()

        self.submodules.phy0 = ttl_simple.Output(self.ttl0)
        self.submodules.phy1 = ttl_simple.Output(self.ttl1)
        self.submodules.phy2 = ttl_simple.Output(self.ttl2)
        self.phy2.rtlink.o.enable_replace = False
        self.submodules.phy3 = BusyPHY()

        rtio_channels = [
            rtio.Channel.from_phy(self.phy0),
            rtio.Channel.from_phy(self.phy1),
            rtio.Channel.from_phy(self.phy2),
            rtio.Channel.from_phy(self.phy3),
        ]

        self.submodules.output_driver = output_driver.OutputDriver(
            rtio_channels, 0, LANE_COUNT, 4*LANE_COUNT)


def simulate(input_events):
    dut = DUT()

    def gen():
        for n, input_event in enumerate(input_events):
            yield dut.output_driver.input[n].valid.eq(1)
            yield dut.output_driver.input[n].seqn.eq(n)
            for k, v in input_event.items():
                yield getattr(dut.output_driver.input[n].payload, k).eq(v)
        yield
        for n in range(len(input_events)):
            yield dut.output_driver.input[n].valid.eq(0)
        for i in range(output_network.latency(LANE_COUNT) + 2):
            yield
        for i in range(3):
            yield

    output = ""

    @passive
    def monitor():
        nonlocal output

        ttls = [dut.ttl0, dut.ttl1, dut.ttl2]
        prev_ttl_values = [0, 0, 0]
        while True:
            ttl_values = []
            for ttl in ttls:
                ttl_values.append((yield ttl))
            for n, (old, new) in enumerate(zip(prev_ttl_values, ttl_values)):
                if old != new:
                    output += "TTL{} {}->{}\n".format(n, old, new)
            prev_ttl_values = ttl_values

            if (yield dut.output_driver.collision):
                output += "collision ch{}\n".format((yield dut.output_driver.collision_channel))
            if (yield dut.output_driver.busy):
                output += "busy ch{}\n".format((yield dut.output_driver.busy_channel))

            yield

    run_simulation(dut, {"sys": [gen(), monitor()]},
                   {"sys": 5, "rio": 5, "rio_phy": 5})
    return output


class TestOutputNetwork(unittest.TestCase):
    def test_one_ttl(self):
        self.assertEqual(
            simulate([{"data": 1}]),
            "TTL0 0->1\n")

    def test_simultaneous_ttl(self):
        self.assertEqual(
            simulate([{"channel": 0, "data": 1},
                      {"channel": 1, "data": 1},
                      {"channel": 2, "data": 1}]),
            "TTL0 0->1\n"
            "TTL1 0->1\n"
            "TTL2 0->1\n")

    def test_replace(self):
        self.assertEqual(
            simulate([{"data": 0},
                      {"data": 1},
                      {"data": 0}]),
            "")
        self.assertEqual(
            simulate([{"data": 1},
                      {"data": 0},
                      {"data": 1}]),
            "TTL0 0->1\n")

    def test_collision(self):
        self.assertEqual(
            simulate([{"channel": 2},
                      {"channel": 2}]),
            "collision ch2\n")

    def test_busy(self):
        self.assertEqual(
            simulate([{"channel": 3}]),
            "busy ch3\n")
