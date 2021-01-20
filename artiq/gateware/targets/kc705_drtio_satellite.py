#!/usr/bin/env python3

import argparse
import os

from migen import *
from migen.build.generic_platform import *
from migen.build.xilinx.vivado import XilinxVivadoToolchain
from migen.build.xilinx.ise import XilinxISEToolchain

from misoc.cores import spi as spi_csr
from misoc.cores import gpio
from misoc.integration.builder import *
from misoc.targets.kc705 import BaseSoC, soc_kc705_args, soc_kc705_argdict

from artiq.gateware import rtio
from artiq.gateware.rtio.phy import ttl_simple
from artiq.gateware.drtio.transceiver import gtx_7series
from artiq.gateware.drtio.siphaser import SiPhaser7Series
from artiq.gateware.drtio.rx_synchronizer import XilinxRXSynchronizer
from artiq.gateware.drtio import *
from artiq.build_soc import *

# DEBUG
from microscope import *


class Satellite(BaseSoC):
    mem_map = {
        "drtioaux":     0x50000000,
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, gateware_identifier_str=None, **kwargs):
        BaseSoC.__init__(self,
                 cpu_type="or1k",
                 sdram_controller_type="minicon",
                 l2_size=128*1024,
                 integrated_sram_size=8192,
                 **kwargs)
        add_identifier(self, gateware_identifier_str=gateware_identifier_str)

        if isinstance(self.platform.toolchain, XilinxVivadoToolchain):
            self.platform.toolchain.bitstream_commands.extend([
                "set_property BITSTREAM.GENERAL.COMPRESS True [current_design]",
            ])
        if isinstance(self.platform.toolchain, XilinxISEToolchain):
            self.platform.toolchain.bitgen_opt += " -g compress"

        platform = self.platform

        self.comb += platform.request("sfp_tx_disable_n").eq(1)
        tx_pads = [platform.request("sfp_tx")]
        rx_pads = [platform.request("sfp_rx")]

        # 1000BASE_BX10 Ethernet compatible, 125MHz RTIO clock
        self.submodules.drtio_transceiver = gtx_7series.GTX(
            clock_pads=platform.request("si5324_clkout"),
            tx_pads=tx_pads,
            rx_pads=rx_pads,
            sys_clk_freq=self.clk_freq)
        self.csr_devices.append("drtio_transceiver")

        self.submodules.rtio_tsc = rtio.TSC("sync", glbl_fine_ts_width=3)
        cdr = ClockDomainsRenamer({"rtio_rx": "rtio_rx0"})

        self.submodules.rx_synchronizer = cdr(XilinxRXSynchronizer())
        self.submodules.drtiosat = cdr(DRTIOSatellite(
            self.rtio_tsc, self.drtio_transceiver.channels[0], self.rx_synchronizer))
        self.csr_devices.append("drtiosat")

        self.submodules.drtioaux0 = cdr(DRTIOAuxController(
            self.drtiosat.link_layer))
        self.csr_devices.append("drtioaux0")
        self.add_wb_slave(self.mem_map["drtioaux"], 0x800,
                          self.drtioaux0.bus)
        self.add_memory_region("drtioaux0_mem", self.mem_map["drtioaux"] | self.shadow_base, 0x800)

        self.config["HAS_DRTIO"] = None
        self.add_csr_group("drtio", ["drtiosat"])
        self.add_csr_group("drtioaux", ["drtioaux0"])
        self.add_memory_group("drtioaux_mem", ["drtioaux0_mem"])

        self.config["RTIO_FREQUENCY"] = str(self.drtio_transceiver.rtio_clk_freq/1e6)
        # Si5324 Phaser
        self.submodules.siphaser = SiPhaser7Series(
            si5324_clkin=platform.request("si5324_clkin"),
            rx_synchronizer=self.rx_synchronizer,
            ultrascale=False,
            rtio_clk_freq=self.drtio_transceiver.rtio_clk_freq)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk, self.siphaser.mmcm_freerun_output)
        self.csr_devices.append("siphaser")
        self.submodules.si5324_rst_n = gpio.GPIOOut(platform.request("si5324").rst_n)
        self.csr_devices.append("si5324_rst_n")
        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1
        self.config["HAS_SI5324"] = None

        self.comb += [
            platform.request("user_sma_clock_p").eq(ClockSignal("rtio_rx0")),
            platform.request("user_sma_clock_n").eq(ClockSignal("rtio"))
        ]

        rtio_clk_period = 1e9/self.drtio_transceiver.rtio_clk_freq
        # Constrain TX & RX timing for the first transceiver channel
        # (First channel acts as master for phase alignment for all channels' TX)
        gtx0 = self.drtio_transceiver.gtxs[0]
        platform.add_period_constraint(gtx0.txoutclk, rtio_clk_period)
        platform.add_period_constraint(gtx0.rxoutclk, rtio_clk_period)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            gtx0.txoutclk, gtx0.rxoutclk)
        # Constrain RX timing for the each transceiver channel
        # (Each channel performs single-lane phase alignment for RX)
        for gtx in self.drtio_transceiver.gtxs[1:]:
            platform.add_period_constraint(gtx.rxoutclk, rtio_clk_period)
            platform.add_false_path_constraints(
                self.crg.cd_sys.clk, gtx.rxoutclk)

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

        self.submodules.local_io = SyncRTIO(self.rtio_tsc, rtio_channels)
        self.comb += self.drtiosat.async_errors.eq(self.local_io.async_errors)
        self.comb += self.drtiosat.cri.connect(self.local_io.cri)


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder / KC705 DRTIO satellite")
    builder_args(parser)
    soc_kc705_args(parser)
    parser.set_defaults(output_dir="artiq_kc705/satellite")
    args = parser.parse_args()

    soc = Satellite(**soc_kc705_argdict(args))
    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
