#!/usr/bin/env python3

# Copyright (C) 2014, 2015 Robert Jordens <jordens@gmail.com>
# Copyright (C) 2014, 2015 M-Labs Limited

import argparse
from fractions import Fraction

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.cdc import MultiReg
from migen.build.generic_platform import *

from misoc.interconnect.csr import *
from misoc.cores import gpio
from misoc.targets.pipistrello import (BaseSoC, soc_pipistrello_args,
                                       soc_pipistrello_argdict)
from misoc.integration.builder import builder_args, builder_argdict

from artiq.gateware.amp import AMPSoC, build_artiq_soc
from artiq.gateware import rtio
from artiq.gateware.rtio.phy import ttl_simple, ttl_serdes_spartan6, dds, spi
from artiq import __version__ as artiq_version


_pmod_spi = [
    ("pmod_spi", 0,
     Subsignal("cs_n", Pins("PMOD:0")),
     Subsignal("mosi", Pins("PMOD:1")),
     Subsignal("miso", Pins("PMOD:2")),
     Subsignal("clk", Pins("PMOD:3")),
     IOStandard("LVTTL")
     ),
    ("pmod_extended_spi", 0,
     Subsignal("cs_n", Pins("PMOD:0")),
     Subsignal("mosi", Pins("PMOD:1")),
     Subsignal("miso", Pins("PMOD:2")),
     Subsignal("clk", Pins("PMOD:3")),
     Subsignal("int", Pins("PMOD:4")),
     Subsignal("rst", Pins("PMOD:5")),
     Subsignal("d0", Pins("PMOD:6")),
     Subsignal("d1", Pins("PMOD:7")),
     IOStandard("LVTTL")
     ),
]


class _RTIOCRG(Module, AutoCSR):
    def __init__(self, platform, clk_freq):
        self._clock_sel = CSRStorage()
        self._pll_reset = CSRStorage(reset=1)
        self._pll_locked = CSRStatus()

        self.clock_domains.cd_rtio = ClockDomain()
        self.clock_domains.cd_rtiox4 = ClockDomain(reset_less=True)
        self.clock_domains.cd_rtiox8 = ClockDomain(reset_less=True)
        self.rtiox4_stb = Signal()
        self.rtiox8_stb = Signal()

        rtio_f = 125*1000*1000
        f = Fraction(rtio_f, clk_freq)
        rtio_internal_clk = Signal()
        rtio_external_clk = Signal()
        ext_clk = platform.request("ext_clk")
        dcm_locked = Signal()
        rtio_clk = Signal()
        pll_locked = Signal()
        pll = Signal(3)
        pll_fb = Signal()
        self.specials += [
            Instance("IBUFG", i_I=ext_clk, o_O=rtio_external_clk),
            Instance("DCM_CLKGEN", p_CLKFXDV_DIVIDE=2,
                     p_CLKFX_DIVIDE=f.denominator, p_CLKFX_MD_MAX=float(f),
                     p_CLKFX_MULTIPLY=f.numerator, p_CLKIN_PERIOD=1e9/clk_freq,
                     p_SPREAD_SPECTRUM="NONE", p_STARTUP_WAIT="FALSE",
                     i_CLKIN=ClockSignal(), o_CLKFX=rtio_internal_clk,
                     i_FREEZEDCM=0, i_RST=ResetSignal(), o_LOCKED=dcm_locked),
            Instance("BUFGMUX",
                     i_I0=rtio_internal_clk, i_I1=rtio_external_clk,
                     i_S=self._clock_sel.storage, o_O=rtio_clk),
            Instance("PLL_ADV", p_SIM_DEVICE="SPARTAN6",
                     p_BANDWIDTH="OPTIMIZED", p_COMPENSATION="INTERNAL",
                     p_REF_JITTER=.01, p_CLK_FEEDBACK="CLKFBOUT",
                     i_DADDR=0, i_DCLK=0, i_DEN=0, i_DI=0, i_DWE=0,
                     i_RST=self._pll_reset.storage | ~dcm_locked, i_REL=0,
                     p_DIVCLK_DIVIDE=1, p_CLKFBOUT_MULT=8,
                     p_CLKFBOUT_PHASE=0., i_CLKINSEL=1,
                     i_CLKIN1=rtio_clk, i_CLKIN2=0,
                     p_CLKIN1_PERIOD=1e9/rtio_f, p_CLKIN2_PERIOD=0.,
                     i_CLKFBIN=pll_fb, o_CLKFBOUT=pll_fb, o_LOCKED=pll_locked,
                     o_CLKOUT0=pll[0], p_CLKOUT0_DUTY_CYCLE=.5,
                     o_CLKOUT1=pll[1], p_CLKOUT1_DUTY_CYCLE=.5,
                     o_CLKOUT2=pll[2], p_CLKOUT2_DUTY_CYCLE=.5,
                     p_CLKOUT0_PHASE=0., p_CLKOUT0_DIVIDE=1,
                     p_CLKOUT1_PHASE=0., p_CLKOUT1_DIVIDE=2,
                     p_CLKOUT2_PHASE=0., p_CLKOUT2_DIVIDE=8),
            Instance("BUFPLL", p_DIVIDE=8,
                     i_PLLIN=pll[0], i_GCLK=self.cd_rtio.clk,
                     i_LOCKED=pll_locked, o_IOCLK=self.cd_rtiox8.clk,
                     o_SERDESSTROBE=self.rtiox8_stb),
            Instance("BUFPLL", p_DIVIDE=4,
                     i_PLLIN=pll[1], i_GCLK=self.cd_rtio.clk,
                     i_LOCKED=pll_locked, o_IOCLK=self.cd_rtiox4.clk,
                     o_SERDESSTROBE=self.rtiox4_stb),
            Instance("BUFG", i_I=pll[2], o_O=self.cd_rtio.clk),
            AsyncResetSynchronizer(self.cd_rtio, ~pll_locked),
            MultiReg(pll_locked, self._pll_locked.status),
        ]

        # ISE infers correct period constraints for cd_rtio.clk from
        # the internal clock. The first two TIGs target just the BUFGMUX.
        platform.add_platform_command(
            """
NET "sys_clk" TNM_NET = "GRPsys_clk";
NET "{ext_clk}" TNM_NET = "GRPext_clk";
TIMESPEC "TSfix_ise1" = FROM "GRPsys_clk" TO "GRPext_clk" TIG;
NET "{int_clk}" TNM_NET = "GRPint_clk";
TIMESPEC "TSfix_ise2" = FROM "GRPsys_clk" TO "GRPint_clk" TIG;
NET "{rtio_clk}" TNM_NET = "GRPrtio_clk";
TIMESPEC "TSfix_ise3" = FROM "GRPrtio_clk" TO "GRPsys_clk" TIG;
TIMESPEC "TSfix_ise4" = FROM "GRPsys_clk" TO "GRPrtio_clk" TIG;
""",
            ext_clk=rtio_external_clk, int_clk=rtio_internal_clk,
            rtio_clk=self.cd_rtio.clk)


_ttl_io = [
    ("ext_clk", 0, Pins("C:15"), IOStandard("LVTTL")),

    ("ttl", 0, Pins("B:0"), IOStandard("LVTTL")),
    ("ttl", 1, Pins("B:1"), IOStandard("LVTTL")),
    ("ttl", 2, Pins("B:2"), IOStandard("LVTTL")),
    ("ttl", 3, Pins("B:3"), IOStandard("LVTTL")),
    ("ttl", 4, Pins("B:4"), IOStandard("LVTTL")),
    ("ttl", 5, Pins("B:5"), IOStandard("LVTTL")),
    ("ttl", 6, Pins("B:6"), IOStandard("LVTTL")),
    ("ttl", 7, Pins("B:7"), IOStandard("LVTTL")),

    ("ttl", 8, Pins("B:8"), IOStandard("LVTTL")),
    ("ttl", 9, Pins("B:9"), IOStandard("LVTTL")),
    ("ttl", 10, Pins("B:10"), IOStandard("LVTTL")),
    ("ttl", 11, Pins("B:11"), IOStandard("LVTTL")),
    ("ttl", 12, Pins("B:12"), IOStandard("LVTTL")),
    ("ttl", 13, Pins("B:13"), IOStandard("LVTTL")),
    ("ttl", 14, Pins("B:14"), IOStandard("LVTTL")),
    ("ttl", 15, Pins("B:15"), IOStandard("LVTTL")),
]


class Demo(BaseSoC, AMPSoC):
    mem_map = {
        "rtio":          0x20000000,  # (shadow @0xa0000000)
        "mailbox":       0x70000000   # (shadow @0xf0000000)
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, cpu_type="or1k", **kwargs):
        BaseSoC.__init__(self,
                         cpu_type=cpu_type,
                         l2_size=64*1024,
                         ident=artiq_version,
                         clk_freq=75*1000*1000,
                         **kwargs)
        AMPSoC.__init__(self)

        platform = self.platform

        platform.toolchain.bitgen_opt += " -g compress"
        platform.toolchain.ise_commands += """
trce -v 12 -fastpaths -tsi {build_name}.tsi -o {build_name}.twr {build_name}.ncd {build_name}.pcf
"""
        platform.add_extension(_ttl_io)
        platform.add_extension(_pmod_spi)

        self.submodules.leds = gpio.GPIOOut(platform.request("user_led", 4))

        self.submodules.rtio_crg = _RTIOCRG(platform, self.clk_freq)
        self.csr_devices.append("rtio_crg")

        # RTIO channels
        rtio_channels = []
        # the last TTL is used for ClockGen
        for i in range(15):
            if i in (0, 1):
                phy = ttl_serdes_spartan6.InOut_4X(platform.request("ttl", i),
                                                   self.rtio_crg.rtiox4_stb)
            elif i in (2,):
                phy = ttl_serdes_spartan6.Output_8X(platform.request("ttl", i),
                                                    self.rtio_crg.rtiox8_stb)
            else:
                phy = ttl_simple.Output(platform.request("ttl", i))

            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy, ofifo_depth=128))

        for led_number in range(4):
            phy = ttl_simple.Output(platform.request("user_led", led_number))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy, ofifo_depth=4))

        phy = ttl_simple.ClockGen(platform.request("ttl", 15))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))

        phy = spi.SPIMaster(self.platform.request("pmod_extended_spi", 0))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(
            phy, ofifo_depth=64, ififo_depth=64))

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.LogChannel())

        # RTIO logic
        self.submodules.rtio_core = rtio.Core(rtio_channels)
        self.csr_devices.append("rtio_core")
        self.submodules.rtio = rtio.KernelInitiator(self.rtio_core.cri)
        self.register_kernel_cpu_csrdevice("rtio")
        self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)
        self.csr_devices.append("rtio_moninj")
        self.submodules.rtio_analyzer = rtio.Analyzer(self.rtio_core.cri,
                                                      self.get_native_sdram_if())
        self.csr_devices.append("rtio_analyzer")


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder / Pipistrello demo")
    builder_args(parser)
    soc_pipistrello_args(parser)
    args = parser.parse_args()

    soc = Demo(**soc_pipistrello_argdict(args))
    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
