#!/usr/bin/env python3

import argparse

from migen import *
from migen.build.generic_platform import *

from misoc.cores import spi as spi_csr
from misoc.cores import gpio
from misoc.integration.soc_sdram import soc_sdram_args, soc_sdram_argdict
from misoc.integration.builder import builder_args, builder_argdict
from misoc.targets.sayma_amc import MiniSoC

from artiq.gateware.amp import AMPSoC, build_artiq_soc
from artiq.gateware import rtio
from artiq.gateware.rtio.phy import ttl_simple
from artiq.gateware.drtio.transceiver import gth_ultrascale
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

        platform = self.platform
        rtio_clk_freq = 150e6

        # Si5324 used as a free-running oscillator, to avoid dependency on RTM.
        self.submodules.si5324_rst_n = gpio.GPIOOut(platform.request("si5324").rst_n)
        self.csr_devices.append("si5324_rst_n")
        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1
        self.config["HAS_SI5324"] = None
        self.config["SI5324_FREE_RUNNING"] = None

        self.comb += platform.request("sfp_tx_disable_n", 0).eq(1)
        self.submodules.transceiver = gth_ultrascale.GTH(
            clock_pads=platform.request("si5324_clkout"),
            tx_pads=[platform.request("sfp_tx", 0)],
            rx_pads=[platform.request("sfp_rx", 0)],
            sys_clk_freq=self.clk_freq,
            rtio_clk_freq=rtio_clk_freq)

        self.submodules.drtio0 = ClockDomainsRenamer({"rtio_rx": "rtio_rx0"})(
            DRTIOMaster(self.transceiver.channels[0]))
        self.csr_devices.append("drtio0")
        self.add_wb_slave(self.mem_map["drtio_aux"], 0x800,
                          self.drtio0.aux_controller.bus)
        self.add_memory_region("drtio0_aux", self.mem_map["drtio_aux"] | self.shadow_base, 0x800)
        self.config["HAS_DRTIO"] = None
        self.add_csr_group("drtio", ["drtio0"])
        self.add_memory_group("drtio_aux", ["drtio0_aux"])

        rtio_clk_period = 1e9/rtio_clk_freq
        for gth in self.transceiver.gths:
            platform.add_period_constraint(gth.txoutclk, rtio_clk_period)
            platform.add_period_constraint(gth.rxoutclk, rtio_clk_period)
            platform.add_false_path_constraints(
                self.crg.cd_sys.clk,
                gth.txoutclk, gth.rxoutclk)

        rtio_channels = []
        for i in range(4):
            phy = ttl_simple.Output(platform.request("user_led", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))
        sma_io = platform.request("sma_io", 0)
        self.comb += sma_io.direction.eq(1)
        phy = ttl_simple.Output(sma_io.level)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))
        sma_io = platform.request("sma_io", 1)
        self.comb += sma_io.direction.eq(0)
        phy = ttl_simple.InOut(sma_io.level)
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
            [self.rtio_core.cri, self.drtio0.cri])
        self.register_kernel_cpu_csrdevice("cri_con")


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder / Sayma DRTIO master")
    builder_args(parser)
    soc_sdram_args(parser)
    args = parser.parse_args()

    soc = Master(**soc_sdram_argdict(args))
    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
