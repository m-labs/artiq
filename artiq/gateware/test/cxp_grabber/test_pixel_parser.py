from migen import *
from artiq.gateware.cxp_grabber.frame import PixelParser
from artiq.gateware.cxp_grabber.core import ROI
from artiq.gateware.test.cxp_grabber.packet_generator import MonoPixelPacketGenerator

import unittest


class DUT(Module):
    def __init__(self, res_width, count_width):
        self.parser = PixelParser(res_width)
        self.roi = ROI(self.parser.source_pixel4x, count_width)
        self.submodules += self.parser, self.roi


class Testbench:
    def __init__(self, res_width, count_width):
        self.dut = DUT(res_width, count_width)
        self.fragment = self.dut.get_fragment()

    def write_frame_info(self, x_size, y_size, pixel_code):
        yield self.dut.parser.x_size.eq(x_size)
        yield self.dut.parser.y_size.eq(y_size)
        yield self.dut.parser.pixel_format_code.eq(pixel_code)
        yield

    def write_frame(self, packet):
        for i, word in enumerate(packet):
            yield self.dut.parser.sink.data.eq(word.data)
            yield self.dut.parser.sink.stb.eq(word.stb)
            yield self.dut.parser.sink.eop.eq(word.eop)
            yield

        yield self.dut.parser.sink.stb.eq(0)  # prevent accidental stb

    def write_roi_cofig(self, x0, y0, x1, y1):
        yield self.dut.roi.cfg.x0.eq(x0)
        yield self.dut.roi.cfg.y0.eq(y0)
        yield self.dut.roi.cfg.x1.eq(x1)
        yield self.dut.roi.cfg.y1.eq(y1)
        yield

    def fetch_roi_output(self):
        return (yield self.dut.roi.out.count)

    def delay(self, cycle):
        for _ in range(cycle):
            yield

    def run(self, gen):
        run_simulation(self.fragment, gen)


class TestPixelParser(unittest.TestCase):
    def test_run(self):
        tb = Testbench(16, 31)

        def gen(x_size, y_size, pixel_width, x0, y0, x1, y1):
            pixel_code = {
                8: 0x0101,
                10: 0x0102,
                12: 0x0103,
                14: 0x0104,
                16: 0x0105,
            }
            expected_count = (x1 - x0) * (y1 - y0) * ((2**pixel_width) - 1)

            yield from tb.write_roi_cofig(x0, y0, x1, y1)

            packet = MonoPixelPacketGenerator(
                x_size, y_size, pixel_width, with_eol_marked=True
            )
            yield from tb.write_frame_info(x_size, y_size, pixel_code[pixel_width])
            yield from tb.write_frame(packet)

            # there is a 6 cycle delay between stbing the last pixel word and roi update is ready
            for _ in range(6):
                yield

            # verify the pixel parser using the roi result
            self.assertEqual((yield from tb.fetch_roi_output()), expected_count)

        for pixel_width, pattern_cnt in [[8, 4], [10, 16], [12, 8], [14, 16], [16, 2]]:
            # start from pattern_cnt to ensure ROI got some pixels to work with
            for res_size in range(pattern_cnt * 1, pattern_cnt * 2):
                tb.run(
                    gen(
                        res_size,
                        res_size,
                        pixel_width,
                        0,
                        0,
                        res_size - 1,
                        res_size - 1,
                    )
                )


if __name__ == "__main__":
    unittest.main()
