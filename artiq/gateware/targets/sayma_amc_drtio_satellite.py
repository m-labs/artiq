#!/usr/bin/env python3

import argparse
import os

from migen import *
from migen.build.generic_platform import *
from misoc.cores import spi as spi_csr
from misoc.cores import gpio
from misoc.integration.soc_sdram import soc_sdram_args, soc_sdram_argdict
from misoc.integration.builder import *
from misoc.targets.sayma_amc import BaseSoC

from artiq.gateware import rtio
from artiq.gateware.rtio.phy import ttl_simple
from artiq.gateware.drtio.transceiver import gth_ultrascale
from artiq.gateware.drtio import DRTIOSatellite
from artiq import __version__ as artiq_version
from artiq import __artiq_dir__ as artiq_dir


class Satellite(BaseSoC):
    mem_map = {
        "drtio_aux": 0x50000000,
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, **kwargs):
        BaseSoC.__init__(self,
                 cpu_type="or1k",
                 sdram_controller_type="minicon",
                 l2_size=128*1024,
                 ident=artiq_version,
                 **kwargs)

        platform = self.platform
        rtio_clk_freq = 150e6

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

        self.submodules.transceiver = gth_ultrascale.GTH(
            clock_pads=platform.request("si5324_clkout"),
            tx_pads=[platform.request("sfp_tx")],
            rx_pads=[platform.request("sfp_rx")],
            sys_clk_freq=self.clk_freq,
            rtio_clk_freq=rtio_clk_freq)
        rx0 = ClockDomainsRenamer({"rtio_rx": "rtio_rx0"})
        self.submodules.drtio0 = rx0(DRTIOSatellite(
            self.transceiver.channels[0], rtio_channels))
        self.csr_devices.append("drtio0")
        self.add_wb_slave(self.mem_map["drtio_aux"], 0x800,
                          self.drtio0.aux_controller.bus)
        self.add_memory_region("drtio0_aux", self.mem_map["drtio_aux"] | self.shadow_base, 0x800)
        self.config["HAS_DRTIO"] = None
        self.add_csr_group("drtio", ["drtio0"])
        self.add_memory_group("drtio_aux", ["drtio0_aux"])

        self.config["RTIO_FREQUENCY"] = str(rtio_clk_freq/1e6)
        si5324_clkin = platform.request("si5324_clkin")
        self.specials += \
            Instance("OBUFDS",
                i_I=ClockSignal("rtio_rx0"),
                o_O=si5324_clkin.p, o_OB=si5324_clkin.n
            )
        self.submodules.si5324_rst_n = gpio.GPIOOut(platform.request("si5324").rst_n)
        self.csr_devices.append("si5324_rst_n")
        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1
        self.config["HAS_SI5324"] = None

        rtio_clk_period = 1e9/rtio_clk_freq
        gth = self.transceiver.gths[0]
        platform.add_period_constraint(gth.txoutclk, rtio_clk_period)
        platform.add_period_constraint(gth.rxoutclk, rtio_clk_period)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            gth.txoutclk, gth.rxoutclk)


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder / Sayma DRTIO satellite")
    builder_args(parser)
    soc_sdram_args(parser)
    args = parser.parse_args()

    soc = Satellite(**soc_sdram_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.add_software_package("satman", os.path.join(artiq_dir, "firmware", "satman"))
    builder.build()


if __name__ == "__main__":
    main()
