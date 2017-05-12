#!/usr/bin/env python3

import argparse

from migen import *

from migen.build.generic_platform import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.cdc import MultiReg
from misoc.targets.kc705 import soc_kc705_args, soc_kc705_argdict
from misoc.integration.builder import builder_args, builder_argdict
from misoc.interconnect.csr import *

from artiq.gateware.amp import build_artiq_soc
from artiq.gateware import rtio
from artiq.gateware.rtio.phy import ttl_simple, spi


from .kc705_dds import _NIST_Ions


class _RTIOCRG(Module, AutoCSR):
    def __init__(self, platform, rtio_internal_clk):
        self._clock_sel = CSRStorage()
        self._pll_reset = CSRStorage(reset=1)
        self._pll_locked = CSRStatus()
        self.clock_domains.cd_rtio = ClockDomain()
        self.clock_domains.cd_rtiox4 = ClockDomain(reset_less=True)

        # 10 MHz when using 125MHz input
        self.clock_domains.cd_ext_clkout = ClockDomain(reset_less=True)

        rtio_external_clk = Signal()

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


_sma_spi = [
    ("sma_spi", 0,
        Subsignal("clk", Pins("Y23")),  # user_sma_gpio_p
        Subsignal("cs_n", Pins("Y24")),  # user_sma_gpio_n
        Subsignal("mosi", Pins("L25")),  # user_sma_clk_p
        Subsignal("miso", Pins("K25")),  # user_sma_clk_n
        IOStandard("LVCMOS25")),
]


class SMA_SPI(_NIST_Ions):
    """
    SPI on 4 SMA for PDQ2 test/demo.
    """
    def __init__(self, cpu_type="or1k", **kwargs):
        _NIST_Ions.__init__(self, cpu_type, **kwargs)

        platform = self.platform
        self.platform.add_extension(_sma_spi)

        rtio_channels = []

        phy = ttl_simple.Output(platform.request("user_led", 2))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))

        ams101_dac = self.platform.request("ams101_dac", 0)
        phy = ttl_simple.Output(ams101_dac.ldac)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))

        phy = spi.SPIMaster(ams101_dac)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(
            phy, ofifo_depth=4, ififo_depth=4))

        phy = spi.SPIMaster(self.platform.request("sma_spi"))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(
            phy, ofifo_depth=128, ififo_depth=128))

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.LogChannel())

        self.add_rtio(rtio_channels)

    def add_rtio(self, rtio_channels):
        self.submodules.rtio_crg = _RTIOCRG(self.platform, self.crg.cd_sys.clk)
        self.csr_devices.append("rtio_crg")
        self.submodules.rtio_core = rtio.Core(rtio_channels)
        self.csr_devices.append("rtio_core")
        self.submodules.rtio = rtio.KernelInitiator()
        self.submodules.rtio_dma = ClockDomainsRenamer("sys_kernel")(
            rtio.DMA(self.get_native_sdram_if()))
        self.register_kernel_cpu_csrdevice("rtio")
        self.register_kernel_cpu_csrdevice("rtio_dma")
        self.submodules.cri_con = rtio.CRIInterconnectShared(
            [self.rtio.cri, self.rtio_dma.cri],
            [self.rtio_core.cri])
        self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)
        self.csr_devices.append("rtio_moninj")

        self.rtio_crg.cd_rtio.clk.attr.add("keep")
        self.platform.add_period_constraint(self.rtio_crg.cd_rtio.clk, 8.)
        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.rtio_crg.cd_rtio.clk)

        self.submodules.rtio_analyzer = rtio.Analyzer(self.rtio_core.cri,
                                                      self.get_native_sdram_if())
        self.csr_devices.append("rtio_analyzer")


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder / "
        "KC705 SMA SPI demo/test for PDQ2")
    builder_args(parser)
    soc_kc705_args(parser)
    args = parser.parse_args()

    soc = SMA_SPI(**soc_kc705_argdict(args))
    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
