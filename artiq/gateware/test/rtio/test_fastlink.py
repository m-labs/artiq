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
                marker = (marker << 1) & 0x7f
                marker |= (yield self.dut.data[1]) & 1
                if marker >> 1 == 0x01:
                    stb += 1
                    if stb >= 3:
                        break
            yield

    def test_frame(self):
        frame = []
        self.dut.comb += self.dut.payload.eq((1 << len(self.dut.payload)) - 1)
        run_simulation(self.dut, self.record_frame(frame),
            clocks={n: 2 for n in ["sys", "rio", "rio_phy"]},
            vcd_name="fastlink.vcd")
        self.assertEqual(len(frame), 8*10//2)
        self.assertEqual([d[0] for d in frame], [0, 0, 3, 3] * 10)
        self.assertEqual([d[1] & 1 for d in frame[4*4 - 1:10*4 - 1:4]],
                         [0, 0, 0, 0, 0, 1])
