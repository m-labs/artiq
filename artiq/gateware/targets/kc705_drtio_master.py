#!/usr/bin/env python3

import argparse

from migen import *
from migen.build.generic_platform import *
from migen.build.xilinx.vivado import XilinxVivadoToolchain
from migen.build.xilinx.ise import XilinxISEToolchain

from misoc.cores import spi as spi_csr
from misoc.cores import gpio
from misoc.integration.builder import *
from misoc.targets.kc705 import MiniSoC, soc_kc705_args, soc_kc705_argdict

from artiq.gateware.amp import AMPSoC
from artiq.gateware import rtio
from artiq.gateware.rtio.phy import ttl_simple
from artiq.gateware.drtio.transceiver import gtx_7series
from artiq.gateware.drtio import *
from artiq.build_soc import *


class Master(MiniSoC, AMPSoC):
    mem_map = {
        "cri_con":      0x10000000,
        "rtio":         0x20000000,
        "rtio_dma":     0x30000000,
        "drtioaux":     0x50000000,
        "mailbox":      0x70000000
    }
    mem_map.update(MiniSoC.mem_map)

    def __init__(self, gateware_identifier_str=None, **kwargs):
        MiniSoC.__init__(self,
                         cpu_type="or1k",
                         sdram_controller_type="minicon",
                         l2_size=128*1024,
                         integrated_sram_size=8192,
                         ethmac_nrxslots=4,
                         ethmac_ntxslots=4,
                         **kwargs)
        AMPSoC.__init__(self)
        add_identifier(self, gateware_identifier_str=gateware_identifier_str)

        if isinstance(self.platform.toolchain, XilinxVivadoToolchain):
            self.platform.toolchain.bitstream_commands.extend([
                "set_property BITSTREAM.GENERAL.COMPRESS True [current_design]",
            ])
        if isinstance(self.platform.toolchain, XilinxISEToolchain):
            self.platform.toolchain.bitgen_opt += " -g compress"

        platform = self.platform

        self.comb += platform.request("sfp_tx_disable_n").eq(1)
        tx_pads = [
            platform.request("sfp_tx"), platform.request("user_sma_mgt_tx")
        ]
        rx_pads = [
            platform.request("sfp_rx"), platform.request("user_sma_mgt_rx")
        ]

        # 1000BASE_BX10 Ethernet compatible, 125MHz RTIO clock
        self.submodules.drtio_transceiver = gtx_7series.GTX(
            clock_pads=platform.request("si5324_clkout"),
            tx_pads=tx_pads,
            rx_pads=rx_pads,
            sys_clk_freq=self.clk_freq)
        self.csr_devices.append("drtio_transceiver")

        self.submodules.rtio_tsc = rtio.TSC("async", glbl_fine_ts_width=3)

        drtio_csr_group = []
        drtioaux_csr_group = []
        drtioaux_memory_group = []
        drtio_cri = []
        for i in range(len(self.drtio_transceiver.channels)):
            core_name = "drtio" + str(i)
            coreaux_name = "drtioaux" + str(i)
            memory_name = "drtioaux" + str(i) + "_mem"
            drtio_csr_group.append(core_name)
            drtioaux_csr_group.append(coreaux_name)
            drtioaux_memory_group.append(memory_name)

            cdr = ClockDomainsRenamer({"rtio_rx": "rtio_rx" + str(i)})

            core = cdr(DRTIOMaster(
                self.rtio_tsc, self.drtio_transceiver.channels[i]))
            setattr(self.submodules, core_name, core)
            drtio_cri.append(core.cri)
            self.csr_devices.append(core_name)

            coreaux = cdr(DRTIOAuxController(core.link_layer))
            setattr(self.submodules, coreaux_name, coreaux)
            self.csr_devices.append(coreaux_name)

            memory_address = self.mem_map["drtioaux"] + 0x800*i
            self.add_wb_slave(memory_address, 0x800,
                              coreaux.bus)
            self.add_memory_region(memory_name, memory_address | self.shadow_base, 0x800)
        self.config["HAS_DRTIO"] = None
        self.config["HAS_DRTIO_ROUTING"] = None
        self.add_csr_group("drtio", drtio_csr_group)
        self.add_csr_group("drtioaux", drtioaux_csr_group)
        self.add_memory_group("drtioaux_mem", drtioaux_memory_group)

        self.config["RTIO_FREQUENCY"] = str(self.drtio_transceiver.rtio_clk_freq/1e6)
        self.submodules.si5324_rst_n = gpio.GPIOOut(platform.request("si5324").rst_n)
        self.csr_devices.append("si5324_rst_n")
        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1
        self.config["HAS_SI5324"] = None
        self.config["SI5324_AS_SYNTHESIZER"] = None

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
                self.crg.cd_sys.clk, gtx0.txoutclk, gtx.rxoutclk)

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

        self.submodules.rtio_core = rtio.Core(self.rtio_tsc, rtio_channels)
        self.csr_devices.append("rtio_core")

        self.submodules.rtio = rtio.KernelInitiator(self.rtio_tsc)
        self.submodules.rtio_dma = ClockDomainsRenamer("sys_kernel")(
            rtio.DMA(self.get_native_sdram_if()))
        self.register_kernel_cpu_csrdevice("rtio")
        self.register_kernel_cpu_csrdevice("rtio_dma")
        self.submodules.cri_con = rtio.CRIInterconnectShared(
            [self.rtio.cri, self.rtio_dma.cri],
            [self.rtio_core.cri] + drtio_cri,
            enable_routing=True)
        self.register_kernel_cpu_csrdevice("cri_con")
        self.submodules.routing_table = rtio.RoutingTableAccess(self.cri_con)
        self.csr_devices.append("routing_table")


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder / KC705 DRTIO master")
    builder_args(parser)
    soc_kc705_args(parser)
    parser.set_defaults(output_dir="artiq_kc705/master")
    args = parser.parse_args()

    soc = Master(**soc_kc705_argdict(args))
    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
