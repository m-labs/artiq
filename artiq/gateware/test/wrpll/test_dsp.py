import unittest

import numpy as np

from migen import *

from artiq.gateware.drtio.wrpll.ddmtd import Collector
from artiq.gateware.drtio.wrpll import thls, filters


class HelperChainTB(Module):
    def __init__(self, N):
        self.tag_ref = Signal(N)
        self.input_stb = Signal()
        self.adpll = Signal((24, True))
        self.out_stb = Signal()

        ###

        self.submodules.collector = Collector(N)
        self.submodules.loop_filter = thls.make(filters.helper, data_width=48)

        self.comb += [
            self.collector.tag_ref.eq(self.tag_ref),
            self.collector.ref_stb.eq(self.input_stb),
            self.collector.main_stb.eq(self.input_stb),
            self.loop_filter.input.eq(self.collector.out_helper << 22),
            self.loop_filter.input_stb.eq(self.collector.out_stb),
            self.adpll.eq(self.loop_filter.output),
            self.out_stb.eq(self.loop_filter.output_stb),
        ]


class TestDSP(unittest.TestCase):
    def test_main_collector(self):
        N = 2
        collector = Collector(N=N)
        # check collector phase unwrapping
        tags = [(0, 0, 0),
                (0, 1, 1),
                (2, 1, -1),
                (3, 1, -2),
                (0, 1, -3),
                (1, 1, -4),
                (2, 1, -5),
                (3, 1, -6),
                (3, 3, -4),
                (0, 0, -4),
                (0, 1, -3),
                (0, 2, -2),
                (0, 3, -1),
                (0, 0, 0)]
        for i in range(10):
            tags.append((i % (2**N), (i+1) % (2**N), 1))

        def generator():
            for tag_ref, tag_main, out in tags:
                yield collector.tag_ref.eq(tag_ref)
                yield collector.tag_main.eq(tag_main)
                yield collector.main_stb.eq(1)
                yield collector.ref_stb.eq(1)

                yield

                yield collector.main_stb.eq(0)
                yield collector.ref_stb.eq(0)

                while not (yield collector.out_stb):
                    yield

                out_main = yield collector.out_main
                self.assertEqual(out_main, out)

        run_simulation(collector, generator())

    def test_helper_collector(self):
        N = 3
        collector = Collector(N=N)
        # check collector phase unwrapping
        tags = [((2**N - 1 - tag) % (2**N), -1) for tag in range(20)]
        tags += [((tags[-1][0] + 1 + tag) % (2**N), 1) for tag in range(20)]
        tags += [((tags[-1][0] - 2 - 2*tag) % (2**N), -2) for tag in range(20)]

        def generator():
            for tag_ref, out in tags:
                yield collector.tag_ref.eq(tag_ref)
                yield collector.main_stb.eq(1)
                yield collector.ref_stb.eq(1)

                yield

                yield collector.main_stb.eq(0)
                yield collector.ref_stb.eq(0)

                while not (yield collector.out_stb):
                    yield

                out_helper = yield collector.out_helper
                self.assertEqual(out_helper, out)

        run_simulation(collector, generator())

    # test helper collector + filter against output from MATLAB model
    def test_helper_chain(self):
        pll = HelperChainTB(15)

        initial_helper_out = -8000
        ref_tags = np.array([
           24778, 16789,  8801,   814, 25596, 17612,  9628,  1646,
           26433, 18453, 10474,  2496, 27287, 19311, 11337,  3364, 28160,
           20190, 12221,  4253, 29054, 21088, 13124,  5161, 29966, 22005,
           14045,  6087, 30897, 22940, 14985,  7031, 31847, 23895, 15944,
            7995,    47, 24869, 16923,  8978,  1035, 25861, 17920,  9981,
            2042, 26873, 18937, 11002,  3069, 27904, 19973, 12042,  4113,
           28953, 21026, 13100,  5175, 30020, 22098, 14177,  6257, 31106,
           23189, 15273,  7358, 32212, 24300, 16388,  8478,   569, 25429,
           17522,  9617,  1712, 26577, 18675, 10774,  2875, 27745, 19848,
           11951,  4056, 28930, 21038, 13147,  5256, 30135, 22247, 14361,
            6475, 31359, 23476, 15595,  7714, 32603, 24725, 16847,  8971,
            1096
        ])
        adpll_sim = np.array([
              8,   24,   41,   57,   74,   91,  107,  124,  140,  157,  173,
            190,  206,  223,  239,  256,  273,  289,  306,  322,  339,  355,
            372,  388,  405,  421,  438,  454,  471,  487,  504,  520,  537,
            553,  570,  586,  603,  619,  636,  652,  668,  685,  701,  718,
            734,  751,  767,  784,  800,  817,  833,  850,  866,  882,  899,
            915,  932,  948,  965,  981,  998, 1014, 1030, 1047, 1063, 1080,
           1096, 1112, 1129, 1145, 1162, 1178, 1194, 1211, 1227, 1244, 1260,
           1276, 1293, 1309, 1326, 1342, 1358, 1375, 1391, 1407, 1424, 1440,
           1457, 1473, 1489, 1506, 1522, 1538, 1555, 1571, 1587, 1604, 1620,
           1636])

        def sim():
            yield pll.collector.out_helper.eq(initial_helper_out)
            for ref_tag, adpll_matlab in zip(ref_tags, adpll_sim):
                # feed collector
                yield pll.tag_ref.eq(int(ref_tag))
                yield pll.input_stb.eq(1)

                yield

                yield pll.input_stb.eq(0)

                while not (yield pll.collector.out_stb):
                    yield

                tag_diff = yield pll.collector.out_helper

                while not (yield pll.loop_filter.output_stb):
                    yield

                adpll_migen = yield pll.adpll
                self.assertEqual(adpll_migen, adpll_matlab)

                yield

        run_simulation(pll, [sim()])
