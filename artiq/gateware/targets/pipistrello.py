#!/usr/bin/env python3.5

# Copyright (C) 2014, 2015 Robert Jordens <jordens@gmail.com>
# Copyright (C) 2014, 2015 M-Labs Limited

import argparse
import os
from fractions import Fraction

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.cdc import MultiReg

from misoc.interconnect.csr import *
from misoc.interconnect import wishbone
from misoc.cores import gpio
from misoc.integration.soc_core import mem_decoder
from misoc.targets.pipistrello import *

from artiq.gateware.soc import AMPSoC
from artiq.gateware import rtio, nist_qc1
from artiq.gateware.rtio.phy import ttl_simple, ttl_serdes_spartan6, dds, spi
from artiq import __artiq_dir__ as artiq_dir
from artiq import __version__ as artiq_version


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
        pmt2 = platform.request("pmt", 2)
        dcm_locked = Signal()
        rtio_clk = Signal()
        pll_locked = Signal()
        pll = Signal(3)
        pll_fb = Signal()
        self.specials += [
            Instance("IBUFG", i_I=pmt2, o_O=rtio_external_clk),
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
        platform.add_platform_command("""
NET "sys_clk" TNM_NET = "GRPsys_clk";
NET "{ext_clk}" TNM_NET = "GRPext_clk";
TIMESPEC "TSfix_ise1" = FROM "GRPsys_clk" TO "GRPext_clk" TIG;
NET "{int_clk}" TNM_NET = "GRPint_clk";
TIMESPEC "TSfix_ise2" = FROM "GRPsys_clk" TO "GRPint_clk" TIG;
NET "{rtio_clk}" TNM_NET = "GRPrtio_clk";
TIMESPEC "TSfix_ise3" = FROM "GRPrtio_clk" TO "GRPsys_clk" TIG;
TIMESPEC "TSfix_ise4" = FROM "GRPsys_clk" TO "GRPrtio_clk" TIG;
""", ext_clk=rtio_external_clk, int_clk=rtio_internal_clk,
     rtio_clk=self.cd_rtio.clk)


class NIST_QC1(BaseSoC, AMPSoC):
    csr_map = {
        "timer_kernel": None,  # mapped on Wishbone instead
        "rtio": None,  # mapped on Wishbone instead
        "rtio_crg": 10,
        "kernel_cpu": 11,
        "rtio_moninj": 12,
        "rtio_analyzer": 13
    }
    csr_map.update(BaseSoC.csr_map)
    mem_map = {
        "timer_kernel":  0x10000000, # (shadow @0x90000000)
        "rtio":          0x20000000, # (shadow @0xa0000000)
        "mailbox":       0x70000000  # (shadow @0xf0000000)
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, cpu_type="or1k", **kwargs):
        BaseSoC.__init__(self,
                         cpu_type=cpu_type,
                         l2_size=64*1024,
                         with_timer=False,
                         ident=artiq_version,
                         **kwargs)
        AMPSoC.__init__(self)

        platform = self.platform

        platform.toolchain.bitgen_opt += " -g compress"
        platform.toolchain.ise_commands += """
trce -v 12 -fastpaths -tsi {build_name}.tsi -o {build_name}.twr {build_name}.ncd {build_name}.pcf
"""
        platform.add_extension(nist_qc1.papilio_adapter_io)

        self.submodules.leds = gpio.GPIOOut(platform.request("user_led", 4))

        self.comb += [
            platform.request("ttl_l_tx_en").eq(1),
            platform.request("ttl_h_tx_en").eq(1)
        ]

        self.submodules.rtio_crg = _RTIOCRG(platform, self.clk_freq)

        # RTIO channels
        rtio_channels = []
        # pmt1 can run on a 8x serdes if pmt0 is not used
        for i in range(2):
            phy = ttl_serdes_spartan6.Inout_4X(platform.request("pmt", i),
                                               self.rtio_crg.rtiox4_stb)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=512,
                                                       ofifo_depth=4))

        # the last TTL is used for ClockGen
        for i in range(15):
            if i in (0, 1):
                phy = ttl_serdes_spartan6.Output_4X(platform.request("ttl", i),
                                                    self.rtio_crg.rtiox4_stb)
            elif i in (2,):  # ttl2 can run on a 8x serdes if xtrig is not used
                phy = ttl_serdes_spartan6.Output_8X(platform.request("ttl", i),
                                                    self.rtio_crg.rtiox8_stb)
            else:
                phy = ttl_simple.Output(platform.request("ttl", i))

            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy, ofifo_depth=256))

        phy = ttl_simple.Output(platform.request("ext_led", 0))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy, ofifo_depth=4))

        for led_number in range(4):
            phy = ttl_simple.Output(platform.request("user_led", led_number))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy, ofifo_depth=4))

        self.config["RTIO_REGULAR_TTL_COUNT"] = len(rtio_channels)

        phy = ttl_simple.ClockGen(platform.request("ttl", 15))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))

        self.config["RTIO_DDS_CHANNEL"] = len(rtio_channels)
        self.config["DDS_CHANNEL_COUNT"] = 8
        self.config["DDS_AD9858"] = True
        dds_pins = platform.request("dds")
        self.comb += dds_pins.p.eq(0)
        phy = dds.AD9858(dds_pins, 8)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy,
                                                   ofifo_depth=512,
                                                   ififo_depth=4))

        pmod = self.platform.request("pmod", 0)
        spi_pins = Module()
        spi_pins.clk = pmod.d[0]
        spi_pins.mosi = pmod.d[1]
        spi_pins.miso = pmod.d[2]
        spi_pins.cs_n = pmod.d[3:]
        phy = spi.SPIMaster(spi_pins)
        self.submodules += phy
        self.config["RTIO_FIRST_SPI_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.Channel.from_phy(
            phy, ofifo_depth=4, ififo_depth=4))

        self.config["RTIO_LOG_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.LogChannel())

        # RTIO core
        self.submodules.rtio = rtio.RTIO(rtio_channels)
        self.config["RTIO_FINE_TS_WIDTH"] = self.rtio.fine_ts_width
        self.config["DDS_RTIO_CLK_RATIO"] = 8 >> self.rtio.fine_ts_width
        self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)

        # CPU connections
        rtio_csrs = self.rtio.get_csrs()
        self.submodules.rtiowb = wishbone.CSRBank(rtio_csrs)
        self.kernel_cpu.add_wb_slave(mem_decoder(self.mem_map["rtio"]),
                                     self.rtiowb.bus)
        self.add_csr_region("rtio", self.mem_map["rtio"] | 0x80000000, 32,
                            rtio_csrs)

        self.submodules.rtio_analyzer = rtio.Analyzer(self.rtio,
            self.get_native_sdram_if())


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ core device builder / Pipistrello "
                    "+ NIST Ions QC1 hardware adapter")
    builder_args(parser)
    soc_pipistrello_args(parser)
    args = parser.parse_args()

    soc = NIST_QC1(**soc_pipistrello_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.add_software_package("liblwip", os.path.join(artiq_dir, "runtime",
                                                         "liblwip"))
    builder.add_software_package("runtime", os.path.join(artiq_dir, "runtime"))
    builder.build()


if __name__ == "__main__":
    main()
