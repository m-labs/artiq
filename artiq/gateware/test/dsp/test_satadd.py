import unittest
import migen as mg

from artiq.gateware.dsp.tools import SatAddMixin


class DUT(mg.Module, SatAddMixin):
    def __init__(self, width):
        self.o = mg.Signal((width, True))
        self.i0 = mg.Signal.like(self.o)
        self.i1 = mg.Signal.like(self.o)
        self.l0 = mg.Signal.like(self.o)
        self.l1 = mg.Signal.like(self.o)
        self.c = mg.Signal(2)
        self.comb += self.o.eq(self.sat_add((self.i0, self.i1),
            width=4, limits=(self.l0, self.l1), clipped=self.c))


class SatAddTest(unittest.TestCase):
    def setUp(self):
        self.dut = DUT(width=4)
        # import migen.fhdl.verilog
        # print(mg.fhdl.verilog.convert(self.dut))

    def _sweep(self):
        def gen():
            for i0 in range(-8, 8):
                yield self.dut.i0.eq(i0)
                for i1 in range(-8, 8):
                    yield self.dut.i1.eq(i1)
                    yield

        def rec():
            l0 = yield self.dut.l0
            l1 = yield self.dut.l1
            for i in range(1 << 8):
                i0 = yield self.dut.i0
                i1 = yield self.dut.i1
                o = yield self.dut.o
                c = yield self.dut.c

                full = i0 + i1
                lim = full
                clip = 0
                if full < l0:
                    lim = l0
                    clip = 1
                if full > l1:
                    lim = l1
                    clip = 2
                with self.subTest(i0=i0, i1=i1):
                    self.assertEqual(lim, o)
                    self.assertEqual(clip, c)
                yield

        mg.run_simulation(self.dut, (gen(), rec()))

    def test_inst(self):
        pass

    def test_run(self):
        self._sweep()

    def test_limits(self):
        for l0 in -8, 0, 1, 7:
            for l1 in -8, 0, 1, 7:
                self.setUp()
                self.dut.l0.reset = l0
                self.dut.l1.reset = l1
                with self.subTest(l0=l0, l1=l1):
                    self._sweep()
