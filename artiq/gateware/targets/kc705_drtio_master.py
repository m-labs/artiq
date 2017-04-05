#!/usr/bin/env python3

import argparse

from migen import *
from migen.build.generic_platform import *

from misoc.cores import spi as spi_csr
from misoc.targets.kc705 import MiniSoC, soc_kc705_args, soc_kc705_argdict
from misoc.integration.soc_core import mem_decoder
from misoc.integration.builder import builder_args, builder_argdict

from artiq.gateware.ad9154_fmc_ebz import ad9154_fmc_ebz
from artiq.gateware.amp import AMPSoC, build_artiq_soc
from artiq.gateware import rtio
from artiq.gateware.rtio.phy import ttl_simple
from artiq.gateware.drtio.transceiver import gtx_7series
from artiq.gateware.drtio import DRTIOMaster
from artiq import __version__ as artiq_version


class Master(MiniSoC, AMPSoC):
    mem_map = {
        "cri_con":       0x10000000,
        "rtio":          0x20000000,
        "rtio_dma":      0x30000000,
        "drtio_aux":     0x50000000,
        "mailbox":       0x70000000
    }
    mem_map.update(MiniSoC.mem_map)

    def __init__(self, cfg, **kwargs):
        MiniSoC.__init__(self,
                         cpu_type="or1k",
                         sdram_controller_type="minicon",
                         l2_size=128*1024,
                         ident=artiq_version,
                         ethmac_nrxslots=4,
                         ethmac_ntxslots=4,
                         **kwargs)
        AMPSoC.__init__(self)

        platform = self.platform

        self.comb += platform.request("sfp_tx_disable_n").eq(1)
        tx_pads = platform.request("sfp_tx")
        rx_pads = platform.request("sfp_rx")
        if cfg == "simple_gbe":
            # GTX_1000BASE_BX10 Ethernet compatible, 62.5MHz RTIO clock
            # simple TTLs
            self.submodules.transceiver = gtx_7series.GTX_1000BASE_BX10(
                clock_pads=platform.request("sgmii_clock"),
                tx_pads=tx_pads,
                rx_pads=rx_pads,
                sys_clk_freq=self.clk_freq,
                clock_div2=True)
        elif cfg == "sawg_3g":
            # 3Gb link, 150MHz RTIO clock
            # with SAWG on local RTIO and AD9154-FMC-EBZ
            platform.add_extension(ad9154_fmc_ebz)
            self.submodules.transceiver = gtx_7series.GTX_3G(
                clock_pads=platform.request("ad9154_refclk"),
                tx_pads=tx_pads,
                rx_pads=rx_pads,
                sys_clk_freq=self.clk_freq)

            ad9154_spi = platform.request("ad9154_spi")
            self.comb += ad9154_spi.en.eq(1)
            self.submodules.converter_spi = spi_csr.SPIMaster(ad9154_spi)
            self.csr_devices.append("converter_spi")
            self.config["CONVERTER_SPI_DAC_CS"] = 0
            self.config["CONVERTER_SPI_CLK_CS"] = 1
            self.config["HAS_AD9516"] = None
        else:
            raise ValueError
        self.submodules.drtio = DRTIOMaster(self.transceiver)
        self.csr_devices.append("drtio")
        self.add_wb_slave(mem_decoder(self.mem_map["drtio_aux"]),
                          self.drtio.aux_controller.bus)
        self.add_memory_region("drtio_aux", self.mem_map["drtio_aux"] | self.shadow_base, 0x800)

        self.comb += [
            platform.request("user_sma_clock_p").eq(ClockSignal("rtio_rx")),
            platform.request("user_sma_clock_n").eq(ClockSignal("rtio"))
        ]

        rtio_clk_period = 1e9/self.transceiver.rtio_clk_freq
        platform.add_period_constraint(self.transceiver.txoutclk, rtio_clk_period)
        platform.add_period_constraint(self.transceiver.rxoutclk, rtio_clk_period)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.transceiver.txoutclk, self.transceiver.rxoutclk)

        rtio_channels = []
        for i in range(8):
            phy = ttl_simple.Output(platform.request("user_led", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))
        for sma in "user_sma_gpio_p", "user_sma_gpio_n":
            phy = ttl_simple.InOut(platform.request(sma))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)
        self.csr_devices.append("rtio_moninj")

        self.submodules.rtio_core = rtio.Core(rtio_channels, 3)
        self.csr_devices.append("rtio_core")

        self.submodules.rtio = rtio.KernelInitiator()
        self.submodules.rtio_dma = ClockDomainsRenamer("sys_kernel")(
            rtio.DMA(self.get_native_sdram_if()))
        self.register_kernel_cpu_csrdevice("rtio")
        self.register_kernel_cpu_csrdevice("rtio_dma")
        self.submodules.cri_con = rtio.CRIInterconnectShared(
            [self.rtio.cri, self.rtio_dma.cri],
            [self.rtio_core.cri, self.drtio.cri])
        self.register_kernel_cpu_csrdevice("cri_con")


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder / KC705 DRTIO master")
    builder_args(parser)
    soc_kc705_args(parser)
    parser.add_argument("-c", "--config", default="simple_gbe",
                        help="configuration: simple_gbe/sawg_3g "
                             "(default: %(default)s)")
    args = parser.parse_args()

    soc = Master(args.config, **soc_kc705_argdict(args))
    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
