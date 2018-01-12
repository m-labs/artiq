#!/usr/bin/env python3

import argparse

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.cdc import MultiReg
from migen.build.generic_platform import *
from migen.build.xilinx.vivado import XilinxVivadoToolchain
from migen.build.xilinx.ise import XilinxISEToolchain

from misoc.interconnect.csr import *
from misoc.cores import gpio
from misoc.targets.kasli import (MiniSoC, soc_kasli_args,
        soc_kasli_argdict)
from misoc.integration.builder import builder_args, builder_argdict

from artiq.gateware.amp import AMPSoC, build_artiq_soc
from artiq.gateware import rtio
from artiq.gateware.rtio.phy import ttl_simple, ttl_serdes_7series, spi
from artiq import __version__ as artiq_version


class _RTIOCRG(Module, AutoCSR):
    def __init__(self, platform, rtio_internal_clk):
        self._clock_sel = CSRStorage()
        self._pll_reset = CSRStorage(reset=1)
        self._pll_locked = CSRStatus()
        self.clock_domains.cd_rtio = ClockDomain()
        self.clock_domains.cd_rtiox4 = ClockDomain(reset_less=True)

        rtio_external_clk = Signal()
        clk_fpgaio_se = Signal()
        clk_fpgaio = platform.request("clk_fpgaio")  # from Si5324
        platform.add_period_constraint(clk_fpgaio.p, 8.0)
        self.specials += [
                Instance("IBUFGDS",
                    p_DIFF_TERM="TRUE", p_IBUF_LOW_PWR="TRUE",
                    i_I=clk_fpgaio.p, i_IB=clk_fpgaio.n, o_O=clk_fpgaio_se),
                Instance("BUFG", i_I=clk_fpgaio_se, o_O=rtio_external_clk),
        ]

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
                     o_CLKOUT0=rtiox4_clk),
            Instance("BUFG", i_I=rtio_clk, o_O=self.cd_rtio.clk),
            Instance("BUFG", i_I=rtiox4_clk, o_O=self.cd_rtiox4.clk),

            AsyncResetSynchronizer(self.cd_rtio, ~pll_locked),
            MultiReg(pll_locked, self._pll_locked.status)
        ]


class _KasliBase(MiniSoC, AMPSoC):
    mem_map = {
        "cri_con":       0x10000000,
        "rtio":          0x20000000,
        "rtio_dma":      0x30000000,
        "mailbox":       0x70000000
    }
    mem_map.update(MiniSoC.mem_map)

    def __init__(self, **kwargs):
        MiniSoC.__init__(self,
                         cpu_type="or1k",
                         sdram_controller_type="minicon",
                         l2_size=128*1024,
                         ident=artiq_version,
                         ethmac_nrxslots=4,
                         ethmac_ntxslots=4,
                         **kwargs)
        AMPSoC.__init__(self)

        self.submodules.leds = gpio.GPIOOut(Cat(
            self.platform.request("user_led", 0)))
        self.csr_devices.append("leds")

        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1

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
        self.register_kernel_cpu_csrdevice("cri_con")
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


def _eem_signal(i):
    n = "d{}".format(i)
    if i == 0:
        n += "_cc"
    return n


def _dio(eem):
    return [(eem, i,
        Subsignal("p", Pins("{}:{}_p".format(eem, _eem_signal(i)))),
        Subsignal("n", Pins("{}:{}_n".format(eem, _eem_signal(i)))),
        IOStandard("LVDS_25"))
        for i in range(8)]


class Opticlock(_KasliBase):
    """
    Opticlock extension variant configuration
    """
    def __init__(self, **kwargs):
        _KasliBase.__init__(self, **kwargs)

        platform = self.platform
        platform.add_extension(_dio("eem0"))
        platform.add_extension(_dio("eem1"))
        platform.add_extension(_dio("eem2"))
        # platform.add_extension(_urukul("eem3", "eem4"))
        # platform.add_extension(_novogorny("eem5"))

        rtio_channels = []
        for eem in "eem0 eem1 eem2".split():
            for i in range(8):
                phy = ttl_serdes_7series.Output_8X(
                        platform.request(eem, i))
                self.submodules += phy
                rtio_channels.append(rtio.Channel.from_phy(phy))

        for i in (1, 2):
            sfp = platform.request("sfp", i)
            phy = ttl_simple.Output(sfp.led)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.LogChannel())

        self.add_rtio(rtio_channels)


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder for Kasli systems")
    builder_args(parser)
    soc_kasli_args(parser)
    parser.add_argument("--variant", default="opticlock",
                        help="extension variant setup: opticlock "
                             "(default: %(default)s)")
    args = parser.parse_args()

    variant = args.variant.lower()
    if variant == "opticlock":
        cls = Opticlock
    else:
        raise SystemExit("Invalid hardware adapter string (--variant)")

    soc = cls(**soc_kasli_argdict(args))
    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
