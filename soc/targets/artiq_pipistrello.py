from migen.fhdl.std import *
from migen.bank.description import *
from migen.bank import wbgen
from mibuild.generic_platform import *

from misoclib.com import gpio
from misoclib.soc import mem_decoder
from targets.pipistrello import BaseSoC

from artiq.gateware import rtio, ad9858


_tester_io = [
    ("ext_led", 0, Pins("B:7"), IOStandard("LVTTL")),

    ("pmt", 0, Pins("C:13"), IOStandard("LVTTL")),
    ("pmt", 1, Pins("C:14"), IOStandard("LVTTL")),
    ("xtrig", 0, Pins("C:12"), IOStandard("LVTTL")),
    ("dds_clock", 0, Pins("C:15"), IOStandard("LVTTL")),

    ("ttl", 0, Pins("C:11"), IOStandard("LVTTL")),
    ("ttl", 1, Pins("C:10"), IOStandard("LVTTL")),
    ("ttl", 2, Pins("C:9"), IOStandard("LVTTL")),
    ("ttl", 3, Pins("C:8"), IOStandard("LVTTL")),
    ("ttl", 4, Pins("C:7"), IOStandard("LVTTL")),
    ("ttl", 5, Pins("C:6"), IOStandard("LVTTL")),
    ("ttl", 6, Pins("C:5"), IOStandard("LVTTL")),
    ("ttl", 7, Pins("C:4"), IOStandard("LVTTL")),
    ("ttl_l_tx_en", 0, Pins("A:9"), IOStandard("LVTTL")),

    ("ttl", 8, Pins("C:3"), IOStandard("LVTTL")),
    ("ttl", 9, Pins("C:2"), IOStandard("LVTTL")),
    ("ttl", 10, Pins("C:1"), IOStandard("LVTTL")),
    ("ttl", 11, Pins("C:0"), IOStandard("LVTTL")),
    ("ttl", 12, Pins("B:4"), IOStandard("LVTTL")),
    ("ttl", 13, Pins("A:11"), IOStandard("LVTTL")),
    ("ttl", 14, Pins("B:5"), IOStandard("LVTTL")),
    ("ttl", 15, Pins("A:10"), IOStandard("LVTTL")),
    ("ttl_h_tx_en", 0, Pins("B:6"), IOStandard("LVTTL")),

    ("dds", 0,
        Subsignal("a", Pins("A:5 B:10 A:6 B:9 A:7 B:8")),
        Subsignal("d", Pins("A:12 B:3 A:13 B:2 A:14 B:1 A:15 B:0")),
        Subsignal("sel", Pins("A:2 B:14 A:1 B:15 A:0")),
        Subsignal("p", Pins("A:8 B:12")),
        Subsignal("fud_n", Pins("B:11")),
        Subsignal("wr_n", Pins("A:4")),
        Subsignal("rd_n", Pins("B:13")),
        Subsignal("rst_n", Pins("A:3")),
        IOStandard("LVTTL")),
]


class _RTIOCRG(Module, AutoCSR):
    def __init__(self, platform):
        self._clock_sel = CSRStorage()
        self.clock_domains.cd_rtio = ClockDomain()

        # 75MHz -> 125MHz
        rtio_internal_clk = Signal()
        self.specials += Instance("DCM_CLKGEN",
                                  p_CLKFXDV_DIVIDE=2,
                                  p_CLKFX_DIVIDE=3,
                                  p_CLKFX_MD_MAX=1.6,
                                  p_CLKFX_MULTIPLY=5,
                                  p_CLKIN_PERIOD=1e3/75,
                                  p_SPREAD_SPECTRUM="NONE",
                                  p_STARTUP_WAIT="FALSE",
                                  i_CLKIN=ClockSignal(),
                                  o_CLKFX=rtio_internal_clk,
                                  i_FREEZEDCM=0,
                                  i_RST=ResetSignal())

        rtio_external_clk = platform.request("dds_clock")
        platform.add_period_constraint(rtio_external_clk, 8.0)
        self.specials += Instance("BUFGMUX",
                                  i_I0=rtio_internal_clk,
                                  i_I1=rtio_external_clk,
                                  i_S=self._clock_sel.storage,
                                  o_O=self.cd_rtio.clk)

        platform.add_platform_command("""
NET "{rtio_clk}" TNM_NET = "GRPrtio_clk";
NET "sys_clk" TNM_NET = "GRPsys_clk";
TIMESPEC "TSfix_ise1" = FROM "GRPrtio_clk" TO "GRPsys_clk" TIG;
TIMESPEC "TSfix_ise2" = FROM "GRPsys_clk" TO "GRPrtio_clk" TIG;
""", rtio_clk=rtio_internal_clk)


class _QcAdapterBase(BaseSoC):
    csr_map = {
        "rtio": None,  # mapped on Wishbone instead
        "rtiocrg": 13
    }
    csr_map.update(BaseSoC.csr_map)

    def __init__(self, platform, cpu_type="or1k", **kwargs):
        BaseSoC.__init__(self, platform, cpu_type=cpu_type, **kwargs)
        platform.add_extension(_tester_io)

        self.submodules.leds = gpio.GPIOOut(Cat(
            platform.request("user_led", 0),
            platform.request("user_led", 1),
        ))

        fud = Signal()
        self.comb += [
            platform.request("ttl_l_tx_en").eq(1),
            platform.request("ttl_h_tx_en").eq(1)
        ]
        rtio_ins = [platform.request("pmt", i) for i in range(2)]
        rtio_ins += [platform.request("xtrig", 0)]
        rtio_outs = [platform.request("ttl", i) for i in range(16)]
        rtio_outs += [fud]
        rtio_outs += [platform.request("ext_led", 0)]
        rtio_outs += [platform.request("user_led", i) for i in range(2, 5)]

        self.submodules.rtiocrg = _RTIOCRG(platform)
        self.submodules.rtiophy = rtio.phy.SimplePHY(
            rtio_ins + rtio_outs,
            output_only_pads=set(rtio_outs))
        self.submodules.rtio = rtio.RTIO(self.rtiophy,
                                         clk_freq=125000000,
                                         ififo_depth=512)

        dds_pads = platform.request("dds")
        self.submodules.dds = ad9858.AD9858(dds_pads)
        self.comb += dds_pads.fud_n.eq(~fud)


class Single(_QcAdapterBase):
    def __init__(self, platform, **kwargs):
        _QcAdapterBase.__init__(self, platform, **kwargs)

        rtio_csrs = self.rtio.get_csrs()
        self.submodules.rtiowb = wbgen.Bank(rtio_csrs)
        self.add_wb_slave(mem_decoder(0xa0000000), self.rtiowb.bus)
        self.add_csr_region("rtio", 0xa0000000, 32, rtio_csrs)

        self.add_wb_slave(mem_decoder(0xb0000000), self.dds.bus)


default_subtarget = Single
