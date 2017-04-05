#!/usr/bin/env python3

import argparse

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.cdc import MultiReg
from migen.genlib.io import DifferentialInput

from jesd204b.common import (JESD204BTransportSettings,
                             JESD204BPhysicalSettings,
                             JESD204BSettings)
from jesd204b.phy.gtx import GTXQuadPLL
from jesd204b.phy import JESD204BPhyTX
from jesd204b.core import JESD204BCoreTX
from jesd204b.core import JESD204BCoreTXControl

from misoc.interconnect.csr import *
from misoc.cores import gpio
from misoc.cores import spi as spi_csr
from misoc.targets.kc705 import MiniSoC, soc_kc705_args, soc_kc705_argdict
from misoc.integration.builder import builder_args, builder_argdict

from artiq.gateware.amp import AMPSoC, build_artiq_soc
from artiq.gateware import rtio
from artiq.gateware.ad9154_fmc_ebz import ad9154_fmc_ebz
from artiq.gateware.rtio.phy import (ttl_simple, ttl_serdes_7series,
                                     sawg)
from artiq import __version__ as artiq_version


class _PhaserCRG(Module, AutoCSR):
    def __init__(self, platform, refclk):
        self._clock_sel = CSRStorage()
        self._pll_reset = CSRStorage(reset=1)
        self._pll_locked = CSRStatus()
        self.clock_domains.cd_rtio = ClockDomain()
        self.clock_domains.cd_rtiox4 = ClockDomain(reset_less=True)

        external_clk = Signal()
        user_sma_clock = platform.request("user_sma_clock")
        platform.add_period_constraint(user_sma_clock.p, 20/3)
        self.specials += Instance("IBUFDS",
                                  i_I=user_sma_clock.p, i_IB=user_sma_clock.n,
                                  o_O=external_clk)

        pll_locked = Signal()
        rtio_clk = Signal()
        rtiox4_clk = Signal()
        self.specials += [
            Instance("PLLE2_ADV",
                     p_STARTUP_WAIT="FALSE", o_LOCKED=pll_locked,

                     p_REF_JITTER1=0.01, p_REF_JITTER2=0.01,
                     p_CLKIN1_PERIOD=20/3, p_CLKIN2_PERIOD=20/3,
                     i_CLKIN1=refclk, i_CLKIN2=external_clk,
                     # Warning: CLKINSEL=0 means CLKIN2 is selected
                     i_CLKINSEL=~self._clock_sel.storage,

                     # VCO @ 1.2GHz when using 150MHz input
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
        self.cd_rtio.clk.attr.add("keep")
        platform.add_period_constraint(self.cd_rtio.clk, 20/3)


class AD9154JESD(Module, AutoCSR):
    def __init__(self, platform):
        self.jreset = CSRStorage(reset=1)
        self.jsync = CSRStatus()

        ps = JESD204BPhysicalSettings(l=4, m=4, n=16, np=16)
        ts = JESD204BTransportSettings(f=2, s=1, k=16, cs=1)
        settings = JESD204BSettings(ps, ts, did=0x5a, bid=0x5)
        linerate = 6e9
        refclk_freq = 150e6
        fabric_freq = 150*1000*1000

        refclk = Signal()
        self.clock_domains.cd_jesd = ClockDomain()
        refclk_pads = platform.request("ad9154_refclk")

        self.specials += [
            Instance("IBUFDS_GTE2", i_CEB=0,
                     i_I=refclk_pads.p, i_IB=refclk_pads.n, o_O=refclk),
            Instance("BUFG", i_I=refclk, o_O=self.cd_jesd.clk),
            AsyncResetSynchronizer(self.cd_jesd, self.jreset.storage),
        ]
        self.cd_jesd.clk.attr.add("keep")
        platform.add_period_constraint(self.cd_jesd.clk, 1e9/refclk_freq)

        qpll = GTXQuadPLL(refclk, refclk_freq, linerate)
        self.submodules += qpll
        self.phys = []
        for i in range(4):
            phy = JESD204BPhyTX(
                qpll, platform.request("ad9154_jesd", i), fabric_freq)
            phy.gtx.cd_tx.clk.attr.add("keep")
            platform.add_period_constraint(phy.gtx.cd_tx.clk, 40*1e9/linerate)
            platform.add_false_path_constraints(self.cd_jesd.clk,
                                                phy.gtx.cd_tx.clk)
            self.phys.append(phy)
        to_jesd = ClockDomainsRenamer("jesd")
        self.submodules.core = to_jesd(JESD204BCoreTX(self.phys, settings,
                                                      converter_data_width=32))
        self.submodules.control = to_jesd(JESD204BCoreTXControl(self.core))

        sync_pads = platform.request("ad9154_sync")
        jsync = Signal()
        self.specials += [
            DifferentialInput(sync_pads.p, sync_pads.n, jsync),
            MultiReg(jsync, self.jsync.status)
        ]

        self.comb += [
            platform.request("ad9154_txen", 0).eq(1),
            platform.request("ad9154_txen", 1).eq(1),
            self.core.start.eq(jsync),
            platform.request("user_led", 3).eq(jsync),
        ]

        # blinking leds for transceiver reset status
        for i in range(4):
            counter = Signal(max=fabric_freq)
            self.comb += platform.request("user_led", 4 + i).eq(counter[-1])
            sync = getattr(self.sync, "phy{}_tx".format(i))
            sync += [
                counter.eq(counter - 1),
                If(counter == 0,
                    counter.eq(fabric_freq - 1)
                )
            ]


class AD9154(Module, AutoCSR):
    def __init__(self, platform):
        self.submodules.jesd = AD9154JESD(platform)

        self.sawgs = [sawg.Channel(width=16, parallelism=2) for i in range(4)]
        self.submodules += self.sawgs

        for conv, ch in zip(self.jesd.core.sink.flatten(), self.sawgs):
            self.sync.jesd += conv.eq(Cat(ch.o))


class Phaser(MiniSoC, AMPSoC):
    mem_map = {
        "cri_con":       0x10000000,
        "rtio":          0x20000000,
        # "rtio_dma":      0x30000000,
        "mailbox":       0x70000000,
        "ad9154":        0x50000000,
    }
    mem_map.update(MiniSoC.mem_map)

    def __init__(self, cpu_type="or1k", **kwargs):
        MiniSoC.__init__(self,
                         cpu_type=cpu_type,
                         sdram_controller_type="minicon",
                         l2_size=128*1024,
                         ident=artiq_version,
                         ethmac_nrxslots=4,
                         ethmac_ntxslots=4,
                         **kwargs)
        AMPSoC.__init__(self)
        self.platform.toolchain.bitstream_commands.extend([
            "set_property BITSTREAM.GENERAL.COMPRESS True [current_design]",
        ])

        platform = self.platform
        platform.add_extension(ad9154_fmc_ebz)

        self.submodules.leds = gpio.GPIOOut(Cat(
            platform.request("user_led", 0),
            platform.request("user_led", 1)))
        self.csr_devices.append("leds")

        i2c = platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1

        ad9154_spi = platform.request("ad9154_spi")
        self.comb += ad9154_spi.en.eq(1)
        self.submodules.converter_spi = spi_csr.SPIMaster(ad9154_spi)
        self.csr_devices.append("converter_spi")
        self.config["CONVERTER_SPI_DAC_CS"] = 0
        self.config["CONVERTER_SPI_CLK_CS"] = 1
        self.config["HAS_AD9516"] = None

        self.submodules.ad9154 = AD9154(platform)
        self.csr_devices.append("ad9154")

        rtio_channels = []

        phy = ttl_serdes_7series.InOut_8X(
            platform.request("user_sma_gpio_n"))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=128))

        phy = ttl_simple.Output(platform.request("user_led", 2))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))

        sysref_pads = platform.request("ad9154_sysref")
        phy = ttl_serdes_7series.Input_8X(sysref_pads.p, sysref_pads.n)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=32,
                                                   ofifo_depth=2))

        self.config["RTIO_FIRST_SAWG_CHANNEL"] = len(rtio_channels)
        rtio_channels.extend(rtio.Channel.from_phy(phy)
                             for sawg in self.ad9154.sawgs
                             for phy in sawg.phys)

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.LogChannel())

        self.submodules.rtio_crg = _PhaserCRG(
            platform, self.ad9154.jesd.cd_jesd.clk)
        self.csr_devices.append("rtio_crg")
        self.submodules.rtio_core = rtio.Core(rtio_channels)
        self.csr_devices.append("rtio_core")
        self.submodules.rtio = rtio.KernelInitiator()
        # self.submodules.rtio_dma = ClockDomainsRenamer("sys_kernel")(
        #     rtio.DMA(self.get_native_sdram_if()))
        self.register_kernel_cpu_csrdevice("rtio")
        # self.register_kernel_cpu_csrdevice("rtio_dma")
        self.submodules.cri_con = rtio.CRIInterconnectShared(
            [self.rtio.cri],  # , self.rtio_dma.cri],
            [self.rtio_core.cri])
        self.register_kernel_cpu_csrdevice("cri_con")
        self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)
        self.csr_devices.append("rtio_moninj")
        self.submodules.rtio_analyzer = rtio.Analyzer(self.rtio_core.cri,
                                                      self.get_native_sdram_if())
        self.csr_devices.append("rtio_analyzer")

        platform.add_false_path_constraints(
            self.crg.cd_sys.clk, self.rtio_crg.cd_rtio.clk)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk, self.ad9154.jesd.cd_jesd.clk)
        for phy in self.ad9154.jesd.phys:
            platform.add_false_path_constraints(
                self.crg.cd_sys.clk, phy.gtx.cd_tx.clk)


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder / KC705 phaser demo")
    builder_args(parser)
    soc_kc705_args(parser)
    args = parser.parse_args()

    soc = Phaser(**soc_kc705_argdict(args))
    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
