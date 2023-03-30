#!/usr/bin/env python3

import argparse

from migen import *
from migen.build.generic_platform import *

from misoc.interconnect.csr import *
from misoc.cores import gpio, timer
from misoc.targets.digilent_genesys2 import MiniSoC
from misoc.integration.builder import builder_args, builder_argdict
from misoc.integration.soc_sdram import *

from artiq.gateware.amp import AMPSoC
from artiq.gateware import rtio
from artiq.gateware.rtio.phy import ttl_simple
from artiq.build_soc import *


class _StandaloneBase(MiniSoC, AMPSoC):
    mem_map = {
        "cri_con":       0x10000000,
        "rtio":          0x20000000,
        "rtio_dma":      0x30000000,
        "mailbox":       0x70000000
    }
    mem_map.update(MiniSoC.mem_map)

    def __init__(self, fmc1_vadj, gateware_identifier_str=None, **kwargs):
        MiniSoC.__init__(self,
                         fmc1_vadj,
                         cpu_type="vexriscv",
                         cpu_bus_width=64,
                         sdram_controller_type="minicon",
                         l2_size=128*1024,
                         integrated_sram_size=8192,
                         ethmac_nrxslots=4,
                         ethmac_ntxslots=4,
                         **kwargs)
        AMPSoC.__init__(self)
        add_identifier(self, gateware_identifier_str=gateware_identifier_str)

        self.submodules.timer1 = timer.Timer()
        self.csr_devices.append("timer1")
        self.interrupt_devices.append("timer1")

        self.submodules.leds = gpio.GPIOOut(Cat(
            self.platform.request("user_led", 0),
            self.platform.request("user_led", 1)))
        self.csr_devices.append("leds")

    def add_rtio(self, rtio_channels):
        self.submodules.rtio_tsc = rtio.TSC(glbl_fine_ts_width=3)
        self.submodules.rtio_core = rtio.Core(self.rtio_tsc, rtio_channels)
        self.csr_devices.append("rtio_core")
        self.submodules.rtio = rtio.KernelInitiator(self.rtio_tsc)
        self.submodules.rtio_dma = ClockDomainsRenamer("sys_kernel")(
            rtio.DMA(self.get_native_sdram_if(), self.cpu_dw))
        self.register_kernel_cpu_csrdevice("rtio")
        self.register_kernel_cpu_csrdevice("rtio_dma")
        self.submodules.cri_con = rtio.CRIInterconnectShared(
            [self.rtio.cri, self.rtio_dma.cri],
            [self.rtio_core.cri])
        self.register_kernel_cpu_csrdevice("cri_con")

        # Only add MonInj core if there is anything to monitor
        if any([len(c.probes) for c in rtio_channels]):
            self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)
            self.csr_devices.append("rtio_moninj")

        self.submodules.rtio_analyzer = rtio.Analyzer(self.rtio_tsc, self.rtio_core.cri,
                                                      self.get_native_sdram_if(), cpu_dw=self.cpu_dw)
        self.csr_devices.append("rtio_analyzer")


class TestVariant(_StandaloneBase):
    def __init__(self, gateware_identifier_str=None, **kwargs):
        _StandaloneBase.__init__(self, gateware_identifier_str, **kwargs)

        rtio_channels = []
        for i in range(2, 7):
            phy = ttl_simple.Output(self.platform.request("user_led", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))
        for i in range(8):
            phy = ttl_simple.InOut(self.platform.request("user_sw", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.LogChannel())

        self.add_rtio(rtio_channels)


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder for Digilent Genesys2 systems")
    builder_args(parser)
    soc_sdram_args(parser)
    parser.set_defaults(output_dir="artiq_genesys2")
    parser.add_argument("--gateware-identifier-str", default=None,
                        help="Override ROM identifier")
    args = parser.parse_args()

    soc = TestVariant(gateware_identifier_str=args.gateware_identifier_str, **soc_sdram_argdict(args))
    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
