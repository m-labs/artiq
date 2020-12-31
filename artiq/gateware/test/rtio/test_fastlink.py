import unittest

from migen import *
from artiq.gateware.rtio.phy.fastlink import *



class TestPhaser(unittest.TestCase):
    def setUp(self):
        self.dut = SerDes(n_data=8, t_clk=8, d_clk=0b00001111,
                          n_frame=10, n_crc=6, poly=0x2f)

    def test_init(self):
        pass

    def record_frame(self, frame):
        clk = 0
        marker = 0
        stb = 0
        while True:
            if stb == 2:
                frame.append((yield self.dut.data))
            clk = (clk << 2) & 0xff
            clk |= (yield self.dut.data[0])
            if clk == 0x0f:
                if marker == 0x01:
                    stb += 1
                    if stb >= 3:
                        break
                # 10/2 + 1 marker bits
                marker = (marker << 1) & 0x3f
                marker |= (yield self.dut.data[1]) & 1
            yield

    def test_frame(self):
        frame = []
        self.dut.comb += self.dut.payload.eq((1 << len(self.dut.payload)) - 1)
        run_simulation(self.dut, self.record_frame(frame),
            clocks={n: 2 for n in ["sys", "rio", "rio_phy"]})
        self.assertEqual(len(frame), 8*10//2)
        self.assertEqual([d[0] for d in frame], [0, 0, 3, 3] * 10)
        self.assertEqual([d[1] & 1 for d in frame[4*4 - 1:10*4 - 1:4]],
                         [0, 0, 0, 0, 0, 1])


class TestFastino(unittest.TestCase):
    def setUp(self):
        self.dut = SerDes(
            n_data=8, t_clk=7, d_clk=0b1100011,
            n_frame=14, n_crc=12, poly=0x80f)

    def test_init(self):
        pass

    def record_frame(self, frame):
        clk = 0
        marker = 0
        stb = 0
        while True:
            if stb == 2:
                frame.append((yield self.dut.data))
            clk = (clk << 2) & 0xff
            clk |= (yield self.dut.data[0])
            if clk in (0b11100011, 0b11000111):
                if marker == 0x01:
                    stb += 1
                    if stb >= 3:
                        break
                # 14/2 + 1 marker bits
                marker = (marker << 1) & 0xff
                if clk & 0b100:
                    marker |= (yield self.dut.data[1]) >> 1
                else:
                    marker |= (yield self.dut.data[1]) & 1
            yield

    def test_frame(self):
        frame = []
        self.dut.comb += self.dut.payload.eq((1 << len(self.dut.payload)) - 1)
        run_simulation(self.dut, self.record_frame(frame),
            clocks={n: 2 for n in ["sys", "rio", "rio_phy"]})
        self.assertEqual(len(frame), 7*14//2)
        self.assertEqual([d[0] for d in frame], [3, 0, 1, 3, 2, 0, 3] * 7)
        self.assertEqual(frame[-1], [3, 3, 1, 1, 1, 2, 1, 0])  # crc12
