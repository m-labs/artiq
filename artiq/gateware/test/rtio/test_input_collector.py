import unittest

from migen import *

from artiq.gateware import rtio
from artiq.gateware.rtio import rtlink
from artiq.gateware.rtio import cri
from artiq.gateware.rtio.input_collector import *


class OscInput(Module):
    def __init__(self):
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(1),
            rtlink.IInterface(1))
        self.overrides = []
        self.probes = []

        # # #

        counter = Signal(2)
        trigger = Signal()
        self.sync += [
            Cat(counter, trigger).eq(counter + 1),
            self.rtlink.i.stb.eq(0),
            If(trigger,
                self.rtlink.i.stb.eq(1),
                self.rtlink.i.data.eq(~self.rtlink.i.data)
            )
        ]


class DUT(Module):
    def __init__(self):
        self.submodules.phy0 = OscInput()
        self.submodules.phy1 = OscInput()
        rtio_channels = [
            rtio.Channel.from_phy(self.phy0, ififo_depth=4),
            rtio.Channel.from_phy(self.phy1, ififo_depth=4)
        ]
        self.submodules.tsc = ClockDomainsRenamer({"rtio": "sys"})(rtio.TSC("sync"))
        self.submodules.input_collector = InputCollector(self.tsc, rtio_channels, "sync")

    @property
    def cri(self):
        return self.input_collector.cri


def simulate(wait_cycles, ts_timeouts):
    result = []
    dut = DUT()
    def gen():
        for _ in range(wait_cycles):
            yield

        for ts_timeout in ts_timeouts:
            yield dut.cri.i_timeout.eq(ts_timeout)
            yield dut.cri.cmd.eq(cri.commands["read"])
            yield
            yield dut.cri.cmd.eq(cri.commands["nop"])
            yield
            while (yield dut.cri.i_status) & 4:
                yield
            status = yield dut.cri.i_status
            if status & 2:
                result.append("overflow")
            elif status & 1:
                result.append("timeout")
            else:
                i_timestamp = yield dut.cri.i_timestamp
                i_data = yield dut.cri.i_data
                result.append((i_timestamp, i_data))

    run_simulation(dut, gen())
    return result


class TestInput(unittest.TestCase):
    def test_get_data(self):
        result = simulate(0, [256]*8)
        self.assertEqual(result, [(n*4+1, n % 2) for n in range(1, 9)])

    def test_timeout(self):
        result = simulate(0, [3, 16])
        self.assertEqual(result, ["timeout", (5, 1)])

    def test_overflow(self):
        result = simulate(32, [256])
        self.assertEqual(result, ["overflow"])
