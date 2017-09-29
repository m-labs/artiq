import unittest
import itertools

from migen import *

from artiq.gateware import rtio
from artiq.gateware.rtio import cri
from artiq.gateware.rtio.sed.core import *
from artiq.gateware.rtio.phy import ttl_simple


class DUT(Module):
    def __init__(self):
        self.ttl0 = Signal()
        self.ttl1 = Signal()

        self.submodules.phy0 = ttl_simple.Output(self.ttl0)
        self.submodules.phy1 = ttl_simple.Output(self.ttl1)

        rtio_channels = [
            rtio.Channel.from_phy(self.phy0),
            rtio.Channel.from_phy(self.phy1)
        ]

        self.submodules.sed = SED(rtio_channels, 0, "sync")
        self.sync += [
            self.sed.coarse_timestamp.eq(self.sed.coarse_timestamp + 1),
            self.sed.minimum_coarse_timestamp.eq(self.sed.coarse_timestamp + 16)
        ]


def simulate(input_events):
    dut = DUT()

    ttl_changes = []
    access_results = []

    def gen():
        yield dut.sed.cri.chan_sel.eq(0)
        for timestamp, data in input_events:
            yield dut.sed.cri.timestamp.eq(timestamp)
            yield dut.sed.cri.o_data.eq(data)
            yield

            yield dut.sed.cri.cmd.eq(cri.commands["write"])
            yield
            yield dut.sed.cri.cmd.eq(cri.commands["nop"])

            access_time = 0
            yield
            while (yield dut.sed.cri.o_status) & 0x01:
                yield
                access_time += 1

            status = (yield dut.sed.cri.o_status)
            access_status = "ok"
            if status & 0x02:
                access_status = "underflow"
            if (yield dut.sed.sequence_error):
                access_status = "sequence_error"

            access_results.append((access_status, access_time))

    @passive
    def monitor():
        old_ttl_state = 0
        for time in itertools.count():
            ttl_state = yield dut.ttl0
            if ttl_state != old_ttl_state:
                ttl_changes.append(time)
            old_ttl_state = ttl_state
            yield

    run_simulation(dut, {"sys": [
        gen(), monitor(),
        (None for _ in range(45))
    ]}, {"sys": 5, "rio": 5, "rio_phy": 5})

    return ttl_changes, access_results


class TestSED(unittest.TestCase):
    def test_sed(self):
        input_events = [(18, 1), (20, 0), (25, 1), (30, 0)]
        latency = 11
        ttl_changes, access_results = simulate(input_events)
        self.assertEqual(ttl_changes, [e[0] + latency for e in input_events])
        self.assertEqual(access_results, [("ok", 0)]*len(input_events))
