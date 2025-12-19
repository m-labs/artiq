#!/usr/bin/env python3

import argparse

from migen import *
from migen.build.generic_platform import *

from misoc.cores import gpio 
from misoc.targets.phaser import BaseSoC
from misoc.integration.builder import builder_args, builder_argdict

from artiq.gateware.amp import AMPSoC
from artiq.gateware import rtio
from artiq.gateware.rtio.xilinx_clocking import fix_serdes_timing_path
from artiq.gateware.rtio.phy import ttl_simple
from artiq.gateware.rtio.phy import spi2 as rtio_spi
from artiq.gateware.drtio.transceiver import eem_serdes
from artiq.gateware.drtio.rx_synchronizer import NoRXSynchronizer
from artiq.gateware.drtio import *
from artiq.gateware.phaser import PhaserMTDDS
from artiq.build_soc import *

class _SatelliteBase(BaseSoC, AMPSoC):
    mem_map = {
        "rtio":          0x20000000,
        "drtioaux":      0x50000000,
        "mailbox":       0x70000000
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(
        self,
        gateware_identifier_str=None,
        use_sma_clkin=False,
        rtio_clk_freq=125e6,
        **kwargs
    ):
        BaseSoC.__init__(self,
            cpu_type="vexriscv",
            cpu_bus_width=64,
            sdram_controller_type="minicon",
            l2_size=128*1024,
            l2_line_size=64,
            clk_freq=rtio_clk_freq,
            **kwargs)
        AMPSoC.__init__(self)
        add_identifier(self, gateware_identifier_str=gateware_identifier_str)

        platform = self.platform

        self.comb += platform.request("clk_sel").eq(1 if use_sma_clkin else 0)
        self.submodules.error_led = gpio.GPIOOut(self.platform.request("user_led", 5))
        self.csr_devices.append("error_led")

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

        self.submodules.eem_transceiver = eem_serdes.EEMSerdes(self.platform, data_pads)
        self.csr_devices.append("eem_transceiver")
        self.config["HAS_DRTIO_EEM"] = None
        self.config["EEM_DRTIO_COUNT"] = 1

        self.submodules.rtio_tsc = rtio.TSC(glbl_fine_ts_width=3)

        cdr = ClockDomainsRenamer({"rtio_rx": "sys"})
        core = cdr(DRTIOSatellite(
            self.rtio_tsc, self.eem_transceiver.channels[0],
            NoRXSynchronizer()))
        self.submodules.drtiosat = core
        self.csr_devices.append("drtiosat")

        self.submodules.drtioaux0 = cdr(DRTIOAuxController(
            core.link_layer, self.cpu_dw))
        self.csr_devices.append("drtioaux0")

        drtio_aux_mem_size = 1024 * 16 # max_packet * 8 buffers * 2 (tx, rx halves)
        memory_address = self.mem_map["drtioaux"]
        self.add_wb_slave(memory_address, drtio_aux_mem_size, self.drtioaux0.bus)
        self.add_memory_region("drtioaux0_mem", memory_address | self.shadow_base, drtio_aux_mem_size)

        self.config["HAS_DRTIO"] = None
        self.add_csr_group("drtioaux", ["drtioaux0"])
        self.add_memory_group("drtioaux_mem", ["drtioaux0_mem"])

        # Async reset gateware if data lane is idle
        self.comb += self.crg.reset.eq(self.eem_transceiver.rst)

        fix_serdes_timing_path(platform)

        self.config["DRTIO_ROLE"] = "satellite"
        self.config["RTIO_FREQUENCY"] = str(rtio_clk_freq/1e6)
        
        self.rtio_channels = []
        print("User LED at RTIO channel 0x{:06x}".format(len(self.rtio_channels)))
        for i in range(5):
            user_led = self.platform.request("user_led", i)
            phy = ttl_simple.Output(user_led)
            self.submodules += phy
            self.rtio_channels.append(rtio.Channel.from_phy(phy))
 

        spi_pins = [
            platform.request("dac_spi"),
            platform.request("trf_spi", 0),
            platform.request("trf_spi", 1),
            platform.request("att_spi", 0),
            platform.request("att_spi", 1),
        ]

        for pin in spi_pins:
            spimaster = rtio_spi.SPIMaster(pin)
            self.submodules += spimaster
            print("PHASER {} at RTIO channel 0x{:06x}".format(pin.name.upper(), len(self.rtio_channels)))
            self.rtio_channels.append(rtio.Channel.from_phy(spimaster))

    def add_rtio(self, rtio_channels, sed_lanes=8):
        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(self.rtio_channels)
        self.rtio_channels.append(rtio.LogChannel())

        # Only add MonInj core if there is anything to monitor
        if any([len(c.probes) for c in rtio_channels]):
            self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)
            self.csr_devices.append("rtio_moninj")

        # satellite (master-controlled) RTIO
        self.submodules.local_io = SyncRTIO(self.rtio_tsc, rtio_channels, lane_count=sed_lanes)
        self.comb += [ 
            self.drtiosat.async_errors.eq(self.local_io.async_errors),
            self.local_io.sed_spread_enable.eq(self.drtiosat.sed_spread_enable.storage)
        ]

        # subkernel RTIO
        self.submodules.rtio = rtio.KernelInitiator(self.rtio_tsc)
        self.register_kernel_cpu_csrdevice("rtio")

        self.submodules.rtio_dma = rtio.DMA(self.get_native_sdram_if(), self.cpu_dw)
        self.csr_devices.append("rtio_dma")
        self.submodules.cri_con = rtio.CRIInterconnectShared(
            [self.drtiosat.cri, self.rtio_dma.cri, self.rtio.cri],
            [self.local_io.cri],
            enable_routing=True)
        self.csr_devices.append("cri_con")
        self.submodules.routing_table = rtio.RoutingTableAccess(self.cri_con)
        self.csr_devices.append("routing_table")

        self.submodules.rtio_analyzer = rtio.Analyzer(self.rtio_tsc, self.local_io.cri,
                                                self.get_native_sdram_if(), cpu_dw=self.cpu_dw)
        self.csr_devices.append("rtio_analyzer")

class MultiToneDDS(_SatelliteBase):
    def __init__(
        self,
        dds_tones=16,
        no_pipelined_dds_adder=False,
        dds_bw_500mhz=False,
        rtio_clk_freq=125e6,
        **kwarg
    ):
        _SatelliteBase.__init__(self, rtio_clk_freq=rtio_clk_freq, **kwarg)
        platform = self.platform

        dds_bandwidth = 500e6 if dds_bw_500mhz else 250e6
        dds_sample_per_cycle = int(dds_bandwidth / rtio_clk_freq)

        adc_pins = platform.request("adc")
        self.submodules.phaser = phaser = PhaserMTDDS(
            platform.request("hw_variant"),
            [platform.request("att_rstn", i) for i in range(2)],
            [platform.request("trf_ctrl", i) for i in range(2)],
            platform.request("dac_data"),
            platform.request("dac_ctrl"),
            adc_pins,
            platform.request("adc_ctrl"),
            dds_tones=dds_tones,
            dds_sample_per_cycle=dds_sample_per_cycle,
            use_pipeline_adder=not no_pipelined_dds_adder,
            sys_clk_freq=rtio_clk_freq
        )
        platform.add_period_constraint(adc_pins.clkout_p, phaser.adc_phy.sck_period)
        platform.add_false_path_constraints(adc_pins.clkout_p, self.crg.cd_sys.clk)

        print("PHASER PHYS at RTIO channel 0x{:06x}".format(len(self.rtio_channels)))
        self.rtio_channels.extend(rtio.Channel.from_phy(phy) for phy in phaser.phys)

        self.add_rtio(self.rtio_channels)

VARIANTS = {"mtdds": MultiToneDDS}


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder for Phaser"
    )
    builder_args(parser)
    parser.set_defaults(output_dir="artiq_phaser")
    parser.add_argument(
        "--gateware-identifier-str", default=None, help="Override ROM identifier"
    )
    parser.add_argument(
        "--use-sma-clkin",
        action="store_true",
        help="Set clock input to SMA (default is mmcx)",
    )

    subparsers = parser.add_subparsers(
        dest="variant", help="Variant to build", required=True
    )

    parser_mtdds = subparsers.add_parser("mtdds", help="Build MuliToneDDS variant")
    parser_mtdds.add_argument("--dds-tones", default=26, help="Number of DDS tones")
    parser_mtdds.add_argument(
        "--no-pipelined-dds-adder",
        action="store_true",
        help="Disable pipelined adder for DDS tones summing. Decrease latency but tightens timing requirement",
    )
    parser_mtdds.add_argument(
        "--dds-bw-500mhz",
        action="store_true",
        help="Set DDS bandwidth to 500 MHz (default is 250 MHz)",
    )
    args = parser.parse_args()

    argdict = dict()
    argdict["gateware_identifier_str"] = args.gateware_identifier_str
    argdict["use_sma_clkin"] = args.use_sma_clkin

    variant = args.variant.lower()
    if variant == "mtdds":
        argdict["no_pipelined_dds_adder"] = args.no_pipelined_dds_adder
        argdict["dds_tones"] = int(args.dds_tones)
        argdict["dds_bw_500mhz"] = args.dds_bw_500mhz

    try:
        cls = VARIANTS[variant]
    except KeyError:
        raise SystemExit("Invalid variant")

    soc = cls(**argdict)
    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
