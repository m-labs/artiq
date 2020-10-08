import numpy as np

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.cdc import MultiReg, PulseSynchronizer
from misoc.interconnect.csr import *

from artiq.gateware.drtio.wrpll.si549 import Si549
from artiq.gateware.drtio.wrpll.ddmtd import DDMTD, Collector
from artiq.gateware.drtio.wrpll import thls, filters


class FrequencyCounter(Module, AutoCSR):
    def __init__(self, timer_width=23, counter_width=23, domains=["helper", "rtio", "rtio_rx0"]):
        for domain in domains:
            name = "counter_" + domain
            counter = CSRStatus(counter_width, name=name)
            setattr(self, name, counter)
        self.update_en = CSRStorage()

        timer = Signal(timer_width)
        timer_tick = Signal()
        self.sync += Cat(timer, timer_tick).eq(timer + 1)

        for domain in domains:
            sync_domain = getattr(self.sync, domain)
            divider = Signal(2)
            sync_domain += divider.eq(divider + 1)

            divided = Signal()
            divided.attr.add("no_retiming")
            sync_domain += divided.eq(divider[-1])
            divided_sys = Signal()
            self.specials += MultiReg(divided, divided_sys)

            divided_sys_r = Signal()
            divided_tick = Signal()
            self.sync += divided_sys_r.eq(divided_sys)
            self.comb += divided_tick.eq(divided_sys & ~divided_sys_r)

            counter = Signal(counter_width)
            counter_csr = getattr(self, "counter_" + domain)
            self.sync += [
                If(timer_tick,
                    If(self.update_en.storage, counter_csr.status.eq(counter)),
                    counter.eq(0),
                ).Else(
                    If(divided_tick, counter.eq(counter + 1))
                )
            ]


class WRPLL(Module, AutoCSR):
    def __init__(self, helper_clk_pads, main_dcxo_i2c, helper_dxco_i2c, ddmtd_inputs, N=15):
        self.helper_reset = CSRStorage(reset=1)
        self.filter_reset = CSRStorage(reset=1)
        self.adpll_offset_helper = CSRStorage(24)
        self.adpll_offset_main = CSRStorage(24)

        self.tag_arm = CSR()
        self.main_diff_tag = CSRStatus(32)
        self.helper_diff_tag = CSRStatus(32)
        self.ref_tag = CSRStatus(N)
        self.main_tag = CSRStatus(N)

        main_diff_tag_32 = Signal((32, True))
        helper_diff_tag_32 = Signal((32, True))
        self.comb += [
            self.main_diff_tag.status.eq(main_diff_tag_32),
            self.helper_diff_tag.status.eq(helper_diff_tag_32)
        ]

        self.clock_domains.cd_helper = ClockDomain()
        self.clock_domains.cd_filter = ClockDomain()
        self.helper_reset.storage.attr.add("no_retiming")
        self.filter_reset.storage.attr.add("no_retiming")
        self.specials += Instance("IBUFGDS",
                i_I=helper_clk_pads.p, i_IB=helper_clk_pads.n,
                o_O=self.cd_helper.clk)
        self.comb += self.cd_filter.clk.eq(self.cd_helper.clk)
        self.specials += [
            AsyncResetSynchronizer(self.cd_helper, self.helper_reset.storage),
            AsyncResetSynchronizer(self.cd_filter, self.filter_reset.storage)
        ]

        self.submodules.helper_dcxo = Si549(helper_dxco_i2c)
        self.submodules.main_dcxo = Si549(main_dcxo_i2c)

        # for diagnostics and PLL initialization
        self.submodules.frequency_counter = FrequencyCounter()

        ddmtd_counter = Signal(N)
        self.sync.helper += ddmtd_counter.eq(ddmtd_counter + 1)
        self.submodules.ddmtd_ref = DDMTD(ddmtd_counter, ddmtd_inputs.rec_clk)
        self.submodules.ddmtd_main = DDMTD(ddmtd_counter, ddmtd_inputs.main_xo)

        filter_cd = ClockDomainsRenamer("filter")
        helper_cd = ClockDomainsRenamer("helper")
        self.submodules.collector = helper_cd(Collector(N))
        self.submodules.filter_helper = filter_cd(
            thls.make(filters.helper, data_width=48))
        self.submodules.filter_main = filter_cd(
            thls.make(filters.main, data_width=48))

        self.comb += [
            self.collector.tag_ref.eq(self.ddmtd_ref.h_tag),
            self.collector.ref_stb.eq(self.ddmtd_ref.h_tag_update),
            self.collector.tag_main.eq(self.ddmtd_main.h_tag),
            self.collector.main_stb.eq(self.ddmtd_main.h_tag_update)
        ]

        collector_stb_ps = PulseSynchronizer("helper", "sys")
        self.submodules += collector_stb_ps
        self.sync.helper += collector_stb_ps.i.eq(self.collector.out_stb)
        collector_stb_sys = Signal()
        self.sync += collector_stb_sys.eq(collector_stb_ps.o)

        main_diff_tag_sys = Signal((N+2, True))
        helper_diff_tag_sys = Signal((N+2, True))
        ref_tag_sys = Signal(N)
        main_tag_sys = Signal(N)
        self.specials += MultiReg(self.collector.out_main, main_diff_tag_sys)
        self.specials += MultiReg(self.collector.out_helper, helper_diff_tag_sys)
        self.specials += MultiReg(self.collector.tag_ref, ref_tag_sys)
        self.specials += MultiReg(self.collector.tag_main, main_tag_sys)

        self.sync += [
            If(self.tag_arm.re & self.tag_arm.r, self.tag_arm.w.eq(1)),
            If(collector_stb_sys,
               self.tag_arm.w.eq(0),
               If(self.tag_arm.w,
                  main_diff_tag_32.eq(main_diff_tag_sys),
                  helper_diff_tag_32.eq(helper_diff_tag_sys),
                  self.ref_tag.status.eq(ref_tag_sys),
                  self.main_tag.status.eq(main_tag_sys)
                 )
              )
        ]

        self.comb += [
            self.filter_helper.input.eq(self.collector.out_helper << 22),
            self.filter_helper.input_stb.eq(self.collector.out_stb),
            self.filter_main.input.eq(self.collector.out_main),
            self.filter_main.input_stb.eq(self.collector.out_stb)
        ]

        self.sync.helper += [
            self.helper_dcxo.adpll_stb.eq(self.filter_helper.output_stb),
            self.helper_dcxo.adpll.eq(self.filter_helper.output + self.adpll_offset_helper.storage),
            self.main_dcxo.adpll_stb.eq(self.filter_main.output_stb),
            self.main_dcxo.adpll.eq(self.filter_main.output + self.adpll_offset_main.storage)
        ]


def helper_sim(N=15):
    class WRPLL(Module):
        def __init__(self, N):
            self.tag_ref = Signal(N)
            self.input_stb = Signal()
            self.adpll = Signal((24, True))
            self.out_stb = Signal()

            # # # #
            loop_filter = thls.make(filters.helper, data_width=48)
            self.submodules.loop_filter = loop_filter
            self.submodules.collector = collector = Collector(N)

            self.comb += [
                self.collector.tag_ref.eq(self.tag_ref),
                self.collector.ref_stb.eq(self.input_stb),
                self.collector.main_stb.eq(self.input_stb),
                self.loop_filter.input.eq(self.collector.out_helper << 22),
                self.loop_filter.input_stb.eq(self.collector.out_stb),
                self.adpll.eq(self.loop_filter.output),
                self.out_stb.eq(self.loop_filter.output_stb),
            ]
    pll = WRPLL(N=N)

    # check filter against output from MatLab model
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
            print("ref tag diff: {}, migen sim adpll {}, matlab adpll {}"
                  .format(tag_diff, adpll_migen, adpll_matlab))

            assert adpll_migen == adpll_matlab
            yield

    run_simulation(pll, [sim()])


if __name__ == "__main__":
    helper_sim()
