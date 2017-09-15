import unittest

from migen import *

from artiq.gateware.rtio import cri
from artiq.gateware.rtio.sed import lane_distributor


LANE_COUNT = 8


def simulate(input_events, wait=True):
    dut = lane_distributor.LaneDistributor(LANE_COUNT, 8, [("channel", 8), ("timestamp", 32)], 3)

    output = []
    access_results = []

    def gen():
        for channel, timestamp in input_events:
            yield dut.cri.chan_sel.eq(channel)
            yield dut.cri.timestamp.eq(timestamp)
            yield

            yield dut.cri.cmd.eq(cri.commands["write"])
            yield
            yield dut.cri.cmd.eq(cri.commands["nop"])

            access_time = 0
            yield
            while (yield dut.cri.o_status) & 0x01:
                yield
                access_time += 1

            status = (yield dut.cri.o_status)
            access_status = "ok"
            if status & 0x02:
                access_status = "underflow"
            if status & 0x04:
                access_status = "sequence_error"

            access_results.append((access_status, access_time))

    @passive
    def monitor_lane(n, lio, wait_time):
        yield lio.writable.eq(1)
        while True:
            while not (yield lio.we):
                yield
            seqn = (yield lio.seqn)
            channel = (yield lio.payload.channel)
            timestamp = (yield lio.payload.timestamp)
            output.append((n, seqn, channel, timestamp))

            yield lio.writable.eq(0)
            for i in range(wait_time):
                yield
            yield lio.writable.eq(1)
            yield

    generators = [gen()]
    for n, lio in enumerate(dut.lane_io):
        lio.writable.reset = 1
        wait_time = 0
        if wait:
            if n == 6:
                wait_time = 1
            elif n == 7:
                wait_time = 4
        generators.append(monitor_lane(n, lio, wait_time))
    run_simulation(dut, generators)

    return output, access_results


class TestLaneDistributor(unittest.TestCase):
    def test_regular(self):
        # Assumes lane 0 does not have wait time.
        N = 16
        output, access_results = simulate([(42+n, (n+1)*8) for n in range(N)])
        self.assertEqual(output, [(0, n, 42+n, (n+1)*8) for n in range(N)])
        self.assertEqual(access_results, [("ok", 0)]*N)

    def test_wait_time(self):
        output, access_results = simulate([(42+n, 8) for n in range(LANE_COUNT)])
        self.assertEqual(output, [(n, n, 42+n, 8) for n in range(LANE_COUNT)])
        expected_access_results = [("ok", 0)]*LANE_COUNT
        expected_access_results[6] = ("ok", 1)
        expected_access_results[7] = ("ok", 4)
        self.assertEqual(access_results, expected_access_results)

    def test_lane_switch(self):
        N = 32
        output, access_results = simulate([(42+n, n+8) for n in range(N)], wait=False)
        self.assertEqual(output, [((n-n//8) % LANE_COUNT, n, 42+n, n+8) for n in range(N)])
        self.assertEqual([ar[0] for ar in access_results], ["ok"]*N)

    def test_sequence_error(self):
        input_events = [(42+n, 8) for n in range(LANE_COUNT+1)]
        input_events.append((42+LANE_COUNT+1, 16))
        output, access_results = simulate(input_events)
        self.assertEqual(len(output), len(input_events)-1)  # event with sequence error must get discarded
        self.assertEqual([ar[0] for ar in access_results[:LANE_COUNT]], ["ok"]*LANE_COUNT)
        self.assertEqual(access_results[LANE_COUNT][0], "sequence_error")

    def test_underflow(self):
        N = 16
        input_events = [(42+n, (n+1)*8) for n in range(N-2)]
        input_events.append((0, 0))  # timestamp < 8 underflows
        input_events.append((42+N-2, N*8))
        output, access_results = simulate(input_events)
        self.assertEqual(len(output), len(input_events)-1)  # event with underflow must get discarded
        self.assertEqual([ar[0] for ar in access_results[:N-2]], ["ok"]*(N-2))
        self.assertEqual(access_results[N-2][0], "underflow")
        self.assertEqual(output[N-2], (0, N-2, 42+N-2, N*8))
        self.assertEqual(access_results[N-1][0], "ok")

    def test_spread(self):
        # get to lane 6
        input_events = [(42+n, 8) for n in range(7)]
        input_events.append((100, 16))
        input_events.append((100, 32))
        output, access_results = simulate(input_events)
        self.assertEqual([o[0] for o in output], [x % LANE_COUNT for x in range(9)])
        self.assertEqual([ar[0] for ar in access_results], ["ok"]*9)
