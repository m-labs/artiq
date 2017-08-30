#!/usr/bin/env python3

import argparse
import os

from migen import *

from misoc.cores import gpio
from misoc.integration.soc_sdram import soc_sdram_args, soc_sdram_argdict
from misoc.integration.builder import builder_args, builder_argdict
from misoc.interconnect import stream
from misoc.targets.sayma_amc import MiniSoC

from artiq.gateware.amp import AMPSoC, build_artiq_soc
from artiq.gateware import serwb
from artiq.gateware import remote_csr
from artiq.gateware import rtio
from artiq.gateware.rtio.phy import ttl_simple
from artiq import __version__ as artiq_version


class SaymaAMCStandalone(MiniSoC, AMPSoC):
    mem_map = {
        "cri_con":       0x10000000,
        "rtio":          0x11000000,
        "rtio_dma":      0x12000000,
        "serwb":         0x13000000,
        "mailbox":       0x70000000
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
        platform = self.platform
        platform.toolchain.bitstream_commands.append(
            "set_property BITSTREAM.GENERAL.COMPRESS True [current_design]")

        self.submodules.leds = gpio.GPIOOut(Cat(
            platform.request("user_led", 0),
            platform.request("user_led", 1)))
        self.csr_devices.append("leds")

        # forward RTM UART to second FTDI UART channel
        serial_1 = platform.request("serial", 1)
        serial_rtm = platform.request("serial_rtm")
        self.comb += [
            serial_1.tx.eq(serial_rtm.rx),
            serial_rtm.tx.eq(serial_1.rx)
        ]

        # AMC/RTM serwb
        # TODO: cleanup (same comments as in sayma_rtm.py)

        # serwb SERDES
        serwb_pll = serwb.phy.SERWBPLL(125e6, 1.25e9, vco_div=1)
        self.comb += serwb_pll.refclk.eq(self.crg.cd_sys.clk)
        self.submodules += serwb_pll

        serwb_pads = platform.request("amc_rtm_serwb")
        serwb_phy = serwb.phy.SERWBPHY(platform.device, serwb_pll, serwb_pads, mode="slave")
        self.submodules.serwb_phy = serwb_phy
        self.csr_devices.append("serwb_phy")

        serwb_phy.serdes.cd_serdes.clk.attr.add("keep")
        serwb_phy.serdes.cd_serdes_20x.clk.attr.add("keep")
        serwb_phy.serdes.cd_serdes_5x.clk.attr.add("keep")
        platform.add_period_constraint(serwb_phy.serdes.cd_serdes.clk, 32.0),
        platform.add_period_constraint(serwb_phy.serdes.cd_serdes_20x.clk, 1.6),
        platform.add_period_constraint(serwb_phy.serdes.cd_serdes_5x.clk, 6.4)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            serwb_phy.serdes.cd_serdes.clk,
            serwb_phy.serdes.cd_serdes_5x.clk)

        # serwb slave
        serwb_core = serwb.core.SERWBCore(serwb_phy, int(self.clk_freq), mode="slave")
        self.submodules += serwb_core
        self.add_wb_slave(self.mem_map["serwb"], 8192, serwb_core.etherbone.wishbone.bus)

        # RTIO
        rtio_channels = []
        for i in (2, 3):
            phy = ttl_simple.Output(platform.request("user_led", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        for i in (0, 1):
            sma_io = platform.request("sma_io", i)
            self.comb += sma_io.direction.eq(1)
            phy = ttl_simple.Output(sma_io.level)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.LogChannel())

        self.clock_domains.cd_rtio = ClockDomain()
        self.comb += [
            self.cd_rtio.clk.eq(ClockSignal()),
            self.cd_rtio.rst.eq(ResetSignal())
        ]
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

        self.submodules.rtio_analyzer = rtio.Analyzer(self.rtio_core.cri,
                                                      self.get_native_sdram_if())
        self.csr_devices.append("rtio_analyzer")


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder / Sayma AMC stand-alone")
    builder_args(parser)
    soc_sdram_args(parser)
    parser.add_argument("--rtm-csr-csv",
        default=os.path.join("artiq_sayma_rtm", "sayma_rtm_csr.csv"),
        help="CSV file listing remote CSRs on RTM (default: %(default)s)")
    args = parser.parse_args()

    soc = SaymaAMCStandalone(**soc_sdram_argdict(args))

    remote_csr_regions = remote_csr.get_remote_csr_regions(
        soc.mem_map["serwb"] | soc.shadow_base,
        args.rtm_csr_csv)
    for name, origin, busword, csrs in remote_csr_regions:
        soc.add_csr_region(name, origin, busword, csrs)

    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
