from migen.fhdl.std import *
from migen.bank.description import *
from migen.bank import wbgen
from mibuild.generic_platform import *

from misoclib.cpu.peripherals import gpio
from targets.kc705 import BaseSoC

from artiqlib import rtio, ad9858


_tester_io = [
    ("pmt", 0, Pins("LPC:LA20_N"), IOStandard("LVTTL")),
    ("pmt", 1, Pins("LPC:LA24_P"), IOStandard("LVTTL")),

    ("ttl", 0, Pins("LPC:LA21_P"), IOStandard("LVTTL")),
    ("ttl", 1, Pins("LPC:LA25_P"), IOStandard("LVTTL")),
    ("ttl", 2, Pins("LPC:LA21_N"), IOStandard("LVTTL")),
    ("ttl", 3, Pins("LPC:LA25_N"), IOStandard("LVTTL")),
    ("ttl", 4, Pins("LPC:LA22_P"), IOStandard("LVTTL")),
    ("ttl", 5, Pins("LPC:LA26_P"), IOStandard("LVTTL")),
    ("ttl", 6, Pins("LPC:LA22_N"), IOStandard("LVTTL")),
    ("ttl", 7, Pins("LPC:LA26_N"), IOStandard("LVTTL")),
    ("ttl", 8, Pins("LPC:LA23_P"), IOStandard("LVTTL")),
    ("ttl", 9, Pins("LPC:LA27_P"), IOStandard("LVTTL")),
    ("ttl", 10, Pins("LPC:LA23_N"), IOStandard("LVTTL")),
    ("ttl", 11, Pins("LPC:LA27_N"), IOStandard("LVTTL")),
    ("ttl", 12, Pins("LPC:LA00_CC_P"), IOStandard("LVTTL")),
    ("ttl", 13, Pins("LPC:LA10_P"), IOStandard("LVTTL")),
    ("ttl", 14, Pins("LPC:LA00_CC_N"), IOStandard("LVTTL")),
    ("ttl", 15, Pins("LPC:LA10_N"), IOStandard("LVTTL")),
    ("ttl_l_tx_en", 0, Pins("LPC:LA11_P"), IOStandard("LVTTL")),
    ("ttl_h_tx_en", 0, Pins("LPC:LA01_CC_P"), IOStandard("LVTTL")),

    ("dds", 0,
        Subsignal("a", Pins("LPC:LA04_N LPC:LA14_N LPC:LA05_P LPC:LA15_P "
                            "LPC:LA05_N LPC:LA15_N")),
        Subsignal("d", Pins("LPC:LA06_P LPC:LA16_P LPC:LA06_N LPC:LA16_N "
                            "LPC:LA07_P LPC:LA17_CC_P LPC:LA07_N "
                            "LPC:LA17_CC_N")),
        Subsignal("sel", Pins("LPC:LA12_N LPC:LA03_P LPC:LA13_P LPC:LA03_N "
                              "LPC:LA13_N")),
        Subsignal("p", Pins("LPC:LA11_N LPC:LA02_P")),
        Subsignal("fud_n", Pins("LPC:LA14_P")),
        Subsignal("wr_n", Pins("LPC:LA04_P")),
        Subsignal("rd_n", Pins("LPC:LA02_N")),
        Subsignal("rst_n", Pins("LPC:LA12_P")),
        IOStandard("LVTTL")),
]


class _RTIOCRG(Module, AutoCSR):
    def __init__(self, platform, rtio_internal_clk):
        self._r_clock_sel = CSRStorage()
        self.clock_domains.cd_rtio = ClockDomain()

        rtio_external_clk = Signal()
        user_sma_clock = platform.request("user_sma_clock")
        platform.add_period_constraint(user_sma_clock.p, 8.0)
        self.specials += Instance("IBUFDS",
                                  i_I=user_sma_clock.p, i_IB=user_sma_clock.n,
                                  o_O=rtio_external_clk)
        self.specials += Instance("BUFGMUX",
                                  i_I0=rtio_internal_clk,
                                  i_I1=rtio_external_clk,
                                  i_S=self._r_clock_sel.storage,
                                  o_O=self.cd_rtio.clk)


class ARTIQSoC(BaseSoC):
    csr_map = {
        "rtio": None,  # mapped on Wishbone instead
        "rtiocrg": 13
    }
    csr_map.update(BaseSoC.csr_map)

    def __init__(self, platform, cpu_type="or1k", with_test_gen=False,
                 **kwargs):
        BaseSoC.__init__(self, platform,
                         cpu_type=cpu_type, **kwargs)
        platform.add_extension(_tester_io)

        self.submodules.leds = gpio.GPIOOut(Cat(
            platform.request("user_led", 0),
            platform.request("user_led", 1)))

        fud = Signal()
        self.comb += [
            platform.request("ttl_l_tx_en").eq(1),
            platform.request("ttl_h_tx_en").eq(1)
        ]
        rtio_ins = [platform.request("pmt") for i in range(2)]
        rtio_outs = [platform.request("ttl", i) for i in range(6)] + [fud]

        self.submodules.rtiocrg = _RTIOCRG(platform, self.crg.pll_sys)
        self.submodules.rtiophy = rtio.phy.SimplePHY(
            rtio_ins + rtio_outs,
            output_only_pads=set(rtio_outs))
        self.submodules.rtio = rtio.RTIO(self.rtiophy,
                                         clk_freq=125000000,
                                         ififo_depth=512)

        rtio_csrs = self.rtio.get_csrs()
        self.submodules.rtiowb = wbgen.Bank(rtio_csrs)
        self.add_wb_slave(lambda a: a[26:29] == 2, self.rtiowb.bus)
        self.add_csr_region("rtio", 0xa0000000, 32, rtio_csrs)

        dds_pads = platform.request("dds")
        self.submodules.dds = ad9858.AD9858(dds_pads)
        self.add_wb_slave(lambda a: a[26:29] == 3, self.dds.bus)
        self.comb += dds_pads.fud_n.eq(~fud)

default_subtarget = ARTIQSoC
