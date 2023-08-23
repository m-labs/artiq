#!/usr/bin/env python3

import argparse

from migen import *
from migen.build.generic_platform import *

from misoc.cores import gpio, spi2
from misoc.targets.efc import BaseSoC
from misoc.integration.builder import builder_args, builder_argdict

from artiq.gateware.amp import AMPSoC
from artiq.gateware import rtio
from artiq.gateware.rtio.xilinx_clocking import fix_serdes_timing_path
from artiq.gateware.drtio.transceiver import eem_serdes
from artiq.gateware.drtio.rx_synchronizer import XilinxRXSynchronizer
from artiq.gateware.drtio import *
from artiq.build_soc import *


class Satellite(BaseSoC, AMPSoC):
    mem_map = {
        "rtio":          0x20000000,
        "drtioaux":      0x50000000,
        "mailbox":       0x70000000
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, gateware_identifier_str=None, **kwargs):
        BaseSoC.__init__(self,
                 cpu_type="vexriscv",
                 cpu_bus_width=64,
                 sdram_controller_type="minicon",
                 l2_size=128*1024,
                 clk_freq=125e6,
                 **kwargs)
        AMPSoC.__init__(self)
        add_identifier(self, gateware_identifier_str=gateware_identifier_str)

        platform = self.platform

        drtio_eem_io = [
            ("drtio_tx", 0,
                Subsignal("p", Pins("eem0:d0_cc_p eem0:d1_p eem0:d2_p eem0:d3_p")),
                Subsignal("n", Pins("eem0:d0_cc_n eem0:d1_n eem0:d2_n eem0:d3_n")),
                IOStandard("LVDS_25"),
            ),
            ("drtio_rx", 0,
                Subsignal("p", Pins("eem0:d4_p eem0:d5_p eem0:d6_p eem0:d7_p")),
                Subsignal("n", Pins("eem0:d4_n eem0:d5_n eem0:d6_n eem0:d7_n")),
                IOStandard("LVDS_25"), Misc("DIFF_TERM=TRUE"),
            ),
        ]

        platform.add_extension(drtio_eem_io)
        data_pads = [
            (platform.request("drtio_rx"), platform.request("drtio_tx"))
        ]

        # Disable SERVMOD, hardwire it to ground to enable EEM 0
        servmod = self.platform.request("servmod")
        self.comb += servmod.eq(0)

        self.submodules.eem_transceiver = eem_serdes.EEMSerdes(self.platform, data_pads)
        self.csr_devices.append("eem_transceiver")
        self.config["HAS_DRTIO_EEM"] = None
        self.config["EEM_DRTIO_COUNT"] = 1

        self.submodules.rtio_tsc = rtio.TSC(glbl_fine_ts_width=3)

        cdr = ClockDomainsRenamer({"rtio_rx": "rtio_rx0"})
        self.submodules.rx_synchronizer = cdr(XilinxRXSynchronizer())
        core = cdr(DRTIOSatellite(
            self.rtio_tsc, self.eem_transceiver.channels[0],
            self.rx_synchronizer))
        self.submodules.drtiosat = core
        self.csr_devices.append("drtiosat")

        self.submodules.drtioaux0 = cdr(DRTIOAuxController(
            core.link_layer, self.cpu_dw))
        self.csr_devices.append("drtioaux0")

        memory_address = self.mem_map["drtioaux"]
        self.add_wb_slave(memory_address, 0x800, self.drtioaux0.bus)
        self.add_memory_region("drtioaux0_mem", memory_address | self.shadow_base, 0x800)

        self.config["HAS_DRTIO"] = None
        self.add_csr_group("drtioaux", ["drtioaux0"])
        self.add_memory_group("drtioaux_mem", ["drtioaux0_mem"])

        i2c = self.platform.request("fpga_i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1

        # Enable I2C
        i2c_reset = self.platform.request("i2c_mux_rst_n")
        self.comb += i2c_reset.eq(1)

        fix_serdes_timing_path(platform)

        self.config["DRTIO_ROLE"] = "satellite"
        self.config["RTIO_FREQUENCY"] = "125.0"

        shuttler_io = [            
            ('dac_spi', 0,
                Subsignal('clk', Pins('fmc0:HB16_N')),
                Subsignal('mosi', Pins('fmc0:HB06_CC_N')),
                Subsignal('cs_n', Pins('fmc0:LA31_N fmc0:LA31_P fmc0:HB19_P fmc0:LA30_P')),
                IOStandard("LVCMOS18")),
            ('dac_rst', 0, Pins('fmc0:HB16_P'), IOStandard("LVCMOS18")),
        ]

        platform.add_extension(shuttler_io)

        self.submodules.converter_spi = spi2.SPIMaster(spi2.SPIInterface(self.platform.request("dac_spi", 0)))
        self.csr_devices.append("converter_spi")
        self.config["HAS_CONVERTER_SPI"] = None

        dac_rst = self.platform.request('dac_rst')
        self.comb += dac_rst.eq(0)

        self.rtio_channels = []

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(self.rtio_channels)
        self.rtio_channels.append(rtio.LogChannel())

        self.add_rtio(self.rtio_channels)

    def add_rtio(self, rtio_channels, sed_lanes=8):
        # Only add MonInj core if there is anything to monitor
        if any([len(c.probes) for c in rtio_channels]):
            self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)
            self.csr_devices.append("rtio_moninj")

        # satellite (master-controlled) RTIO
        self.submodules.local_io = SyncRTIO(self.rtio_tsc, rtio_channels, lane_count=sed_lanes)
        self.comb += self.drtiosat.async_errors.eq(self.local_io.async_errors)

        # subkernel RTIO
        self.submodules.rtio = rtio.KernelInitiator(self.rtio_tsc)
        self.register_kernel_cpu_csrdevice("rtio")

        self.submodules.rtio_dma = rtio.DMA(self.get_native_sdram_if(), self.cpu_dw)
        self.csr_devices.append("rtio_dma")
        self.submodules.cri_con = rtio.CRIInterconnectShared(
            [self.drtiosat.cri, self.rtio_dma.cri],
            [self.local_io.cri],
            enable_routing=True)
        self.csr_devices.append("cri_con")
        self.submodules.routing_table = rtio.RoutingTableAccess(self.cri_con)
        self.csr_devices.append("routing_table")

        self.submodules.rtio_analyzer = rtio.Analyzer(self.rtio_tsc, self.local_io.cri,
                                                self.get_native_sdram_if(), cpu_dw=self.cpu_dw)
        self.csr_devices.append("rtio_analyzer")


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder for EEM FMC Carrier systems")
    builder_args(parser)
    parser.set_defaults(output_dir="artiq_efc")
    parser.add_argument("--gateware-identifier-str", default=None,
                        help="Override ROM identifier")
    args = parser.parse_args()

    argdict = dict()
    argdict["gateware_identifier_str"] = args.gateware_identifier_str

    soc = Satellite(**argdict)
    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
