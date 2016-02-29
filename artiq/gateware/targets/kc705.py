#!/usr/bin/env python3.5

import argparse
import os

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.cdc import MultiReg
from migen.build.generic_platform import *
from migen.build.xilinx.vivado import XilinxVivadoToolchain
from migen.build.xilinx.ise import XilinxISEToolchain

from misoc.interconnect.csr import *
from misoc.interconnect import wishbone
from misoc.cores import gpio
from misoc.integration.soc_core import mem_decoder
from misoc.integration.builder import *
from misoc.targets.kc705 import MiniSoC, soc_kc705_args, soc_kc705_argdict

from artiq.gateware.soc import AMPSoC
from artiq.gateware import rtio, nist_qc1, nist_clock, nist_qc2
from artiq.gateware.rtio.phy import ttl_simple, ttl_serdes_7series, dds, spi
from artiq import __artiq_dir__ as artiq_dir
from artiq import __version__ as artiq_version


class _RTIOCRG(Module, AutoCSR):
    def __init__(self, platform, rtio_internal_clk):
        self._clock_sel = CSRStorage()
        self._pll_reset = CSRStorage(reset=1)
        self._pll_locked = CSRStatus()
        self.clock_domains.cd_rtio = ClockDomain()
        self.clock_domains.cd_rtiox4 = ClockDomain(reset_less=True)

        # 10 MHz when using 125MHz input
        self.clock_domains.cd_ext_clkout = ClockDomain(reset_less=True)
        ext_clkout = platform.request("user_sma_gpio_p")
        self.sync.ext_clkout += ext_clkout.eq(~ext_clkout)


        rtio_external_clk = Signal()
        user_sma_clock = platform.request("user_sma_clock")
        platform.add_period_constraint(user_sma_clock.p, 8.0)
        self.specials += Instance("IBUFDS",
                                  i_I=user_sma_clock.p, i_IB=user_sma_clock.n,
                                  o_O=rtio_external_clk)

        pll_locked = Signal()
        rtio_clk = Signal()
        rtiox4_clk = Signal()
        ext_clkout_clk = Signal()
        self.specials += [
            Instance("PLLE2_ADV",
                     p_STARTUP_WAIT="FALSE", o_LOCKED=pll_locked,

                     p_REF_JITTER1=0.01,
                     p_CLKIN1_PERIOD=8.0, p_CLKIN2_PERIOD=8.0,
                     i_CLKIN1=rtio_internal_clk, i_CLKIN2=rtio_external_clk,
                     # Warning: CLKINSEL=0 means CLKIN2 is selected
                     i_CLKINSEL=~self._clock_sel.storage,

                     # VCO @ 1GHz when using 125MHz input
                     p_CLKFBOUT_MULT=8, p_DIVCLK_DIVIDE=1,
                     i_CLKFBIN=self.cd_rtio.clk,
                     i_RST=self._pll_reset.storage,

                     o_CLKFBOUT=rtio_clk,

                     p_CLKOUT0_DIVIDE=2, p_CLKOUT0_PHASE=0.0,
                     o_CLKOUT0=rtiox4_clk,

                     p_CLKOUT1_DIVIDE=50, p_CLKOUT1_PHASE=0.0,
                     o_CLKOUT1=ext_clkout_clk),
            Instance("BUFG", i_I=rtio_clk, o_O=self.cd_rtio.clk),
            Instance("BUFG", i_I=rtiox4_clk, o_O=self.cd_rtiox4.clk),
            Instance("BUFG", i_I=ext_clkout_clk, o_O=self.cd_ext_clkout.clk),

            AsyncResetSynchronizer(self.cd_rtio, ~pll_locked),
            MultiReg(pll_locked, self._pll_locked.status)
        ]


_ams101_dac = [
    ("ams101_dac", 0,

        Subsignal("ldac", Pins("XADC:GPIO0")),
        Subsignal("clk", Pins("XADC:GPIO1")),
        Subsignal("mosi", Pins("XADC:GPIO2")),
        Subsignal("cs_n", Pins("XADC:GPIO3")),
        IOStandard("LVTTL")
     )
]


class _NIST_Ions(MiniSoC, AMPSoC):
    csr_map = {
        "rtio": None,  # mapped on Wishbone instead
        "rtio_crg": 13,
        "kernel_cpu": 14,
        "rtio_moninj": 15,
        "rtio_analyzer": 16
    }
    csr_map.update(MiniSoC.csr_map)
    mem_map = {
        "rtio":     0x20000000, # (shadow @0xa0000000)
        "mailbox":  0x70000000  # (shadow @0xf0000000)
    }
    mem_map.update(MiniSoC.mem_map)

    def __init__(self, cpu_type="or1k", **kwargs):
        MiniSoC.__init__(self,
                         cpu_type=cpu_type,
                         sdram_controller_type="minicon",
                         l2_size=128*1024,
                         with_timer=False,
                         ident=artiq_version,
                         **kwargs)
        AMPSoC.__init__(self)
        if isinstance(self.platform.toolchain, XilinxVivadoToolchain):
            self.platform.toolchain.bitstream_commands.extend([
                "set_property BITSTREAM.GENERAL.COMPRESS True [current_design]",
            ])
        if isinstance(self.platform.toolchain, XilinxISEToolchain):
            self.platform.toolchain.bitgen_opt += " -g compress"

        self.submodules.leds = gpio.GPIOOut(Cat(
            self.platform.request("user_led", 0),
            self.platform.request("user_led", 1)))

        self.platform.add_extension(_ams101_dac)

    def add_rtio(self, rtio_channels):
        self.submodules.rtio_crg = _RTIOCRG(self.platform, self.crg.cd_sys.clk)
        self.submodules.rtio = rtio.RTIO(rtio_channels)
        self.config["RTIO_FINE_TS_WIDTH"] = self.rtio.fine_ts_width
        self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)

        if isinstance(self.platform.toolchain, XilinxVivadoToolchain):
            self.platform.add_platform_command("""
create_clock -name rsys_clk -period 8.0 [get_nets {rsys_clk}]
create_clock -name rio_clk -period 8.0 [get_nets {rio_clk}]
set_false_path -from [get_clocks rsys_clk] -to [get_clocks rio_clk]
set_false_path -from [get_clocks rio_clk] -to [get_clocks rsys_clk]
""", rsys_clk=self.rtio.cd_rsys.clk, rio_clk=self.rtio.cd_rio.clk)
        if isinstance(self.platform.toolchain, XilinxISEToolchain):
            self.platform.add_platform_command("""
NET "sys_clk" TNM_NET = "GRPrsys_clk";
NET "{rio_clk}" TNM_NET = "GRPrio_clk";
TIMESPEC "TSfix_cdc1" = FROM "GRPrsys_clk" TO "GRPrio_clk" TIG;
TIMESPEC "TSfix_cdc2" = FROM "GRPrio_clk" TO "GRPrsys_clk" TIG;
""", rio_clk=self.rtio_crg.cd_rtio.clk)

        rtio_csrs = self.rtio.get_csrs()
        self.submodules.rtiowb = wishbone.CSRBank(rtio_csrs)
        self.kernel_cpu.add_wb_slave(mem_decoder(self.mem_map["rtio"]),
                                     self.rtiowb.bus)
        self.add_csr_region("rtio", self.mem_map["rtio"] | 0x80000000, 32,
                            rtio_csrs)

        self.submodules.rtio_analyzer = rtio.Analyzer(self.rtio,
            self.get_native_sdram_if())


class NIST_QC1(_NIST_Ions):
    """
    NIST QC1 hardware, as used in the Penning lab, with FMC to SCSI cables
    adapter.
    """
    def __init__(self, cpu_type="or1k", **kwargs):
        _NIST_Ions.__init__(self, cpu_type, **kwargs)

        platform = self.platform
        platform.add_extension(nist_qc1.fmc_adapter_io)

        self.comb += [
            platform.request("ttl_l_tx_en").eq(1),
            platform.request("ttl_h_tx_en").eq(1)
        ]

        rtio_channels = []
        for i in range(2):
            phy = ttl_serdes_7series.Inout_8X(platform.request("pmt", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=512))
        for i in range(15):
            phy = ttl_serdes_7series.Output_8X(platform.request("ttl", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        phy = ttl_serdes_7series.Inout_8X(platform.request("user_sma_gpio_n"))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=512))
        phy = ttl_simple.Output(platform.request("user_led", 2))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))
        self.config["RTIO_REGULAR_TTL_COUNT"] = len(rtio_channels)

        phy = ttl_simple.ClockGen(platform.request("ttl", 15))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))

        self.config["RTIO_DDS_CHANNEL"] = len(rtio_channels)
        self.config["DDS_CHANNEL_COUNT"] = 8
        self.config["DDS_AD9858"] = True
        phy = dds.AD9858(platform.request("dds"), 8)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy,
                                                   ofifo_depth=512,
                                                   ififo_depth=4))

        self.config["RTIO_LOG_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.LogChannel())

        self.add_rtio(rtio_channels)
        assert self.rtio.fine_ts_width <= 3
        self.config["DDS_RTIO_CLK_RATIO"] = 8 >> self.rtio.fine_ts_width


class NIST_CLOCK(_NIST_Ions):
    """
    NIST clock hardware, with old backplane and 11 DDS channels
    """
    def __init__(self, cpu_type="or1k", **kwargs):
        _NIST_Ions.__init__(self, cpu_type, **kwargs)

        platform = self.platform
        platform.add_extension(nist_clock.fmc_adapter_io)

        rtio_channels = []
        for i in range(16):
            if i % 4 == 3:
                phy = ttl_serdes_7series.Inout_8X(platform.request("ttl", i))
                self.submodules += phy
                rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=512))
            else:
                phy = ttl_serdes_7series.Output_8X(platform.request("ttl", i))
                self.submodules += phy
                rtio_channels.append(rtio.Channel.from_phy(phy))

        for i in range(2):
            phy = ttl_serdes_7series.Inout_8X(platform.request("pmt", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=512))

        phy = ttl_serdes_7series.Inout_8X(platform.request("user_sma_gpio_n"))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=512))

        phy = ttl_simple.Output(platform.request("user_led", 2))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))

        spi_pins = self.platform.request("ams101_dac", 0)
        phy = ttl_simple.Output(spi_pins.ldac)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))
        self.config["RTIO_REGULAR_TTL_COUNT"] = len(rtio_channels)

        phy = spi.SPIMaster(spi_pins)
        self.submodules += phy
        self.config["RTIO_FIRST_SPI_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.Channel.from_phy(
            phy, ofifo_depth=4, ififo_depth=4))

        phy = ttl_simple.ClockGen(platform.request("la32_p"))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))

        self.config["RTIO_DDS_CHANNEL"] = len(rtio_channels)
        self.config["DDS_CHANNEL_COUNT"] = 11
        self.config["DDS_AD9914"] = True
        self.config["DDS_ONEHOT_SEL"] = True
        phy = dds.AD9914(platform.request("dds"), 11, onehot=True)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy,
                                                   ofifo_depth=512,
                                                   ififo_depth=4))

        self.config["RTIO_LOG_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.LogChannel())

        self.add_rtio(rtio_channels)
        assert self.rtio.fine_ts_width <= 3
        self.config["DDS_RTIO_CLK_RATIO"] = 24 >> self.rtio.fine_ts_width


class NIST_QC2(_NIST_Ions):
    """
    NIST QC2 hardware, as used in Quantum I and Quantum II, with new backplane
    and 12 DDS channels.  Current implementation for single backplane.  
    """
    def __init__(self, cpu_type="or1k", **kwargs):
        _NIST_Ions.__init__(self, cpu_type, **kwargs)

        platform = self.platform
        platform.add_extension(nist_qc2.fmc_adapter_io)

        rtio_channels = []
        # TTL0-23 are In+Out capable
        for i in range(24):
            phy = ttl_serdes_7series.Inout_8X(platform.request("ttl", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=512))
        # TTL24-26 are output only
        for i in range(24, 27):
            phy = ttl_serdes_7series.Output_8X(platform.request("ttl", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        phy = ttl_serdes_7series.Inout_8X(platform.request("user_sma_gpio_n"))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=512))
        phy = ttl_simple.Output(platform.request("user_led", 2))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))
        self.config["RTIO_REGULAR_TTL_COUNT"] = len(rtio_channels)

        # TTL27 is for the clock generator
        phy = ttl_simple.ClockGen(platform.request("ttl", 27))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))

        self.config["RTIO_DDS_CHANNEL"] = len(rtio_channels)
        self.config["DDS_CHANNEL_COUNT"] = 12
        self.config["DDS_AD9914"] = True
        self.config["DDS_ONEHOT_SEL"] = True
        phy = dds.AD9914(platform.request("dds"), 12, onehot=True)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy,
                                                   ofifo_depth=512,
                                                   ififo_depth=4))

        self.config["RTIO_LOG_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.LogChannel())

        self.add_rtio(rtio_channels)
        assert self.rtio.fine_ts_width <= 3
        self.config["DDS_RTIO_CLK_RATIO"] = 24 >> self.rtio.fine_ts_width


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ core device builder / KC705 "
                    "+ NIST Ions QC1/CLOCK/QC2 hardware adapters")
    builder_args(parser)
    soc_kc705_args(parser)
    parser.add_argument("-H", "--hw-adapter", default="clock",
                        help="hardware adapter type: qc1/clock/qc2 "
                             "(default: %(default)s)")
    args = parser.parse_args()

    hw_adapter = args.hw_adapter.lower()
    if hw_adapter == "qc1":
        cls = NIST_QC1
    elif hw_adapter == "clock":
        cls = NIST_CLOCK
    elif hw_adapter == "qc2":
        cls = NIST_QC2
    else:
        print("Invalid hardware adapter string (-H/--hw-adapter), "
              "choose from qc1, clock or qc2")
        sys.exit(1)

    soc = cls(**soc_kc705_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.add_software_package("liblwip", os.path.join(artiq_dir, "runtime",
                                                         "liblwip"))
    builder.add_software_package("runtime", os.path.join(artiq_dir, "runtime"))
    builder.build()


if __name__ == "__main__":
    main()
