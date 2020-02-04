#!/usr/bin/env python3

import argparse

from migen import *

from misoc.cores import gpio
from misoc.integration.builder import builder_args, builder_argdict
from misoc.interconnect.csr import *
from misoc.targets.metlino import *

from artiq.gateware.amp import AMPSoC
from artiq.gateware import eem
from artiq.gateware import rtio
from artiq.gateware.rtio.phy import ttl_simple, ttl_serdes_ultrascale
from artiq.gateware.drtio.transceiver import gth_ultrascale
from artiq.gateware.drtio import *
from artiq.build_soc import *


def workaround_us_lvds_tristate(platform):
    # Those shoddy Kintex Ultrascale FPGAs take almost a microsecond to change the direction of a
    # LVDS I/O buffer. The application has to cope with it and this cannot be handled at static
    # timing analysis. Disable the latter for IOBUFDS.
    # See:
    # https://forums.xilinx.com/t5/Timing-Analysis/Delay-890-ns-in-OBUFTDS-in-Kintex-UltraScale/td-p/868364
    platform.add_platform_command(
        "set_false_path -through [get_pins -filter {{REF_PIN_NAME == T}} -of [get_cells -filter {{REF_NAME == IOBUFDS}}]]")


class Master(MiniSoC, AMPSoC):
    mem_map = {
        "cri_con":       0x10000000,
        "rtio":          0x11000000,
        "rtio_dma":      0x12000000,
        "drtioaux":      0x14000000,
        "mailbox":       0x70000000
    }
    mem_map.update(MiniSoC.mem_map)

    def __init__(self, **kwargs):
        MiniSoC.__init__(self,
                         cpu_type="or1k",
                         sdram_controller_type="minicon",
                         l2_size=128*1024,
                         integrated_sram_size=8192,
                         ethmac_nrxslots=4,
                         ethmac_ntxslots=4,
                         **kwargs)
        AMPSoC.__init__(self)
        add_identifier(self)

        platform = self.platform
        rtio_clk_freq = 150e6

        self.comb += platform.request("input_clk_sel").eq(1)
        self.comb += platform.request("filtered_clk_sel").eq(1)
        self.submodules.si5324_rst_n = gpio.GPIOOut(platform.request("si5324").rst_n)
        self.csr_devices.append("si5324_rst_n")
        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1
        self.config["HAS_SI5324"] = None
        self.config["SI5324_AS_SYNTHESIZER"] = None
        self.config["RTIO_FREQUENCY"] = str(rtio_clk_freq/1e6)

        self.submodules.drtio_transceiver = gth_ultrascale.GTH(
            clock_pads=platform.request("cdr_clk_clean", 0),
            # use only a few channels to work around Vivado bug
            data_pads=[platform.request("mch_fabric_d", i) for i in range(3)],
            sys_clk_freq=self.clk_freq,
            rtio_clk_freq=rtio_clk_freq)
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

            core = cdr(DRTIOMaster(self.rtio_tsc, self.drtio_transceiver.channels[i]))
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

        rtio_clk_period = 1e9/rtio_clk_freq
        gth0 = self.drtio_transceiver.gths[0]
        platform.add_period_constraint(gth0.txoutclk, rtio_clk_period/2)
        platform.add_period_constraint(gth0.rxoutclk, rtio_clk_period)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            gth0.txoutclk, gth0.rxoutclk)
        for gth in self.drtio_transceiver.gths[1:]:
            platform.add_period_constraint(gth.rxoutclk, rtio_clk_period)
            platform.add_false_path_constraints(
                self.crg.cd_sys.clk, gth0.txoutclk, gth.rxoutclk)

        self.rtio_channels = rtio_channels = []
        for i in range(4):
            phy = ttl_simple.Output(platform.request("user_led", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        eem.DIO.add_std(self, 2, ttl_simple.Output, ttl_simple.Output,
                        iostandard="LVDS")
        eem.Urukul.add_std(self, 0, 1, ttl_simple.Output,
                           iostandard="LVDS")
        eem.Zotino.add_std(self, 3, ttl_simple.Output,
                           iostandard="LVDS")
        workaround_us_lvds_tristate(platform)

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.LogChannel())

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
        description="Metlino gateware and firmware builder")
    builder_args(parser)
    soc_sdram_args(parser)
    parser.set_defaults(output_dir="artiq_metlino")
    args = parser.parse_args()
    args.variant = "master"
    soc = Master(**soc_sdram_argdict(args))
    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
