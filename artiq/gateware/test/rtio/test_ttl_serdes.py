import unittest

from migen import *

from artiq.gateware.rtio.phy.ttl_serdes_generic import *


class _FakeSerdes:
    def __init__(self):
        self.o = Signal(8)
        self.i = Signal(8)
        self.oe = Signal()


class _TB(Module):
    def __init__(self):
        self.serdes = _FakeSerdes()
        self.submodules.dut = ClockDomainsRenamer({"rio_phy": "sys", "rio": "sys"})(
            InOut(self.serdes))


class TestTTLSerdes(unittest.TestCase):
    def test_input(self):
        tb = _TB()

        def gen():
            yield tb.dut.rtlink.o.address.eq(2)
            yield tb.dut.rtlink.o.data.eq(0b11)
            yield tb.dut.rtlink.o.stb.eq(1)  # set sensitivity to rising + falling
            yield
            yield tb.dut.rtlink.o.stb.eq(0)
            yield

            self.assertEqual((yield tb.serdes.oe), 0)
            self.assertEqual((yield tb.dut.rtlink.i.stb), 0)

            yield tb.serdes.i.eq(0b11111110)  # rising edge at fine_ts = 1
            yield
            yield tb.serdes.i.eq(0b11111111)
            yield
            self.assertEqual((yield tb.dut.rtlink.i.stb), 1)
            self.assertEqual((yield tb.dut.rtlink.i.fine_ts), 1)

            yield tb.serdes.i.eq(0b01111111)  # falling edge at fine_ts = 7
            yield
            yield tb.serdes.i.eq(0b00000000)
            yield
            self.assertEqual((yield tb.dut.rtlink.i.stb), 1)
            self.assertEqual((yield tb.dut.rtlink.i.fine_ts), 7)

            yield tb.serdes.i.eq(0b11000000)  # rising edge at fine_ts = 6
            yield
            yield tb.serdes.i.eq(0b11111111)
            yield
            self.assertEqual((yield tb.dut.rtlink.i.stb), 1)
            self.assertEqual((yield tb.dut.rtlink.i.fine_ts), 6)

            yield tb.dut.rtlink.o.address.eq(2)
            yield tb.dut.rtlink.o.data.eq(0b01)
            yield tb.dut.rtlink.o.stb.eq(1)  # set sensitivity to rising only
            yield
            yield tb.dut.rtlink.o.stb.eq(0)
            yield

            yield tb.serdes.i.eq(0b00001111)  # falling edge at fine_ts = 4
            yield
            yield tb.serdes.i.eq(0b00000000)
            yield
            # no strobe, sensitivity is rising edge
            self.assertEqual((yield tb.dut.rtlink.i.stb), 0)

            yield tb.serdes.i.eq(0b11110000)  # rising edge at fine_ts = 4
            yield
            yield tb.serdes.i.eq(0b11111111)
            yield
            self.assertEqual((yield tb.dut.rtlink.i.stb), 1)
            self.assertEqual((yield tb.dut.rtlink.i.fine_ts), 4)

        run_simulation(tb, gen())

    def test_output(self):
        tb = _TB()

        def gen():
            yield tb.dut.rtlink.o.address.eq(1)
            yield tb.dut.rtlink.o.data.eq(1)
            yield tb.dut.rtlink.o.stb.eq(1)  # set Output Enable to 1
            yield
            yield tb.dut.rtlink.o.stb.eq(0)
            yield
            yield
            self.assertEqual((yield tb.serdes.oe), 1)

            yield tb.dut.rtlink.o.address.eq(0)
            yield tb.dut.rtlink.o.data.eq(1)
            yield tb.dut.rtlink.o.fine_ts.eq(3)
            yield tb.dut.rtlink.o.stb.eq(1)  # rising edge at fine_ts = 3
            yield
            yield tb.dut.rtlink.o.stb.eq(0)
            yield
            self.assertEqual((yield tb.serdes.o), 0b11111000)

            yield
            self.assertEqual((yield tb.serdes.o), 0b11111111)  # stays at 1
            
            yield tb.dut.rtlink.o.data.eq(0)
            yield tb.dut.rtlink.o.fine_ts.eq(0)
            yield tb.dut.rtlink.o.stb.eq(1)  # falling edge at fine_ts = 0
            yield
            yield tb.dut.rtlink.o.stb.eq(0)
            yield
            self.assertEqual((yield tb.serdes.o), 0b00000000)

            yield
            self.assertEqual((yield tb.serdes.o), 0b00000000)
            
            yield tb.dut.rtlink.o.data.eq(1)
            yield tb.dut.rtlink.o.fine_ts.eq(7)
            yield tb.dut.rtlink.o.stb.eq(1)  # rising edge at fine_ts = 7
            yield
            yield tb.dut.rtlink.o.stb.eq(0)
            yield
            self.assertEqual((yield tb.serdes.o), 0b10000000)

        run_simulation(tb, gen())
