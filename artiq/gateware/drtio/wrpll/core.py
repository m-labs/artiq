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
        self.collector_reset = CSRStorage(reset=1)
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
        self.clock_domains.cd_collector = ClockDomain()
        self.clock_domains.cd_filter = ClockDomain()
        self.helper_reset.storage.attr.add("no_retiming")
        self.filter_reset.storage.attr.add("no_retiming")
        self.specials += Instance("IBUFGDS",
                i_I=helper_clk_pads.p, i_IB=helper_clk_pads.n,
                o_O=self.cd_helper.clk)
        self.comb += [
            self.cd_collector.clk.eq(self.cd_collector.clk),
            self.cd_filter.clk.eq(self.cd_helper.clk),
        ]
        self.specials += [
            AsyncResetSynchronizer(self.cd_helper, self.helper_reset.storage),
            AsyncResetSynchronizer(self.cd_collector, self.collector_reset.storage),
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

        collector_cd = ClockDomainsRenamer("collector")
        filter_cd = ClockDomainsRenamer("filter")
        self.submodules.collector = collector_cd(Collector(N))
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
