from migen.fhdl.std import *
from mibuild.generic_platform import *

from misoclib import gpio
from targets.ppro import BaseSoC

from artiqlib import rtio, ad9858


_tester_io = [
    ("user_led", 1, Pins("B:7"), IOStandard("LVTTL")),
    ("ttl", 0, Pins("C:13"), IOStandard("LVTTL")),
    ("ttl", 1, Pins("C:11"), IOStandard("LVTTL")),
    ("ttl", 2, Pins("C:10"), IOStandard("LVTTL")),
    ("ttl", 3, Pins("C:9"), IOStandard("LVTTL")),
    ("ttl", 4, Pins("C:8"), IOStandard("LVTTL")),
    ("ttl_tx_en", 0, Pins("A:9"), IOStandard("LVTTL")),
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


class _TestGen(Module):
    def __init__(self, pad):
        divc = Signal(15)
        ce = Signal()
        self.sync += Cat(divc, ce).eq(divc + 1)

        sr = Signal(8, reset=0b10101000)
        self.sync += If(ce, sr.eq(Cat(sr[1:], sr[0])))
        self.comb += pad.eq(sr[0])


class _RTIOMiniCRG(Module):
    def __init__(self, platform):
        self.clock_domains.cd_rtio = ClockDomain()
        # 80MHz -> 125MHz
        self.specials += Instance("DCM_CLKGEN",
            p_CLKFXDV_DIVIDE=2, p_CLKFX_DIVIDE=16, p_CLKFX_MD_MAX=1.6, p_CLKFX_MULTIPLY=25,
            p_CLKIN_PERIOD=12.5, p_SPREAD_SPECTRUM="NONE", p_STARTUP_WAIT="FALSE",

            i_CLKIN=ClockSignal(), o_CLKFX=self.cd_rtio.clk,
            i_FREEZEDCM=0, i_RST=ResetSignal())
        platform.add_platform_command("""
NET "{rtio_clk}" TNM_NET = "GRPrtio_clk";
NET "sys_clk" TNM_NET = "GRPsys_clk";
TIMESPEC "TSfix_ise1" = FROM "GRPrtio_clk" TO "GRPsys_clk" TIG;
TIMESPEC "TSfix_ise2" = FROM "GRPsys_clk" TO "GRPrtio_clk" TIG;
""", rtio_clk=self.cd_rtio.clk)


class ARTIQMiniSoC(BaseSoC):
    csr_map = {
        "rtio":            13
    }
    csr_map.update(BaseSoC.csr_map)

    def __init__(self, platform, cpu_type="or1k", ramcon_type="minicon",
                 with_test_gen=False, **kwargs):
        BaseSoC.__init__(self, platform,
                         cpu_type=cpu_type, ramcon_type=ramcon_type,
                         **kwargs)
        platform.add_extension(_tester_io)

        self.submodules.leds = gpio.GPIOOut(Cat(
            platform.request("user_led", 0),
            platform.request("user_led", 1)))

        self.comb += platform.request("ttl_tx_en").eq(1)
        rtio_pads = [platform.request("ttl", i) for i in range(4)]
        fud = Signal()
        rtio_pads.append(fud)
        self.submodules.rtiocrg = _RTIOMiniCRG(platform)
        self.submodules.rtiophy = rtio.phy.SimplePHY(
            rtio_pads,
            output_only_pads={rtio_pads[1], rtio_pads[2], rtio_pads[3], fud})
        self.submodules.rtio = rtio.RTIO(self.rtiophy, 125000000)

        if with_test_gen:
            self.submodules.test_gen = _TestGen(platform.request("ttl", 4))

        dds_pads = platform.request("dds")
        self.submodules.dds = ad9858.AD9858(dds_pads)
        self.add_wb_slave(lambda a: a[26:29] == 3, self.dds.bus)
        self.comb += dds_pads.fud_n.eq(~fud)

default_subtarget = ARTIQMiniSoC
