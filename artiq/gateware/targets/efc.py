#!/usr/bin/env python3

import argparse

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.build.generic_platform import *

from misoc.cores import gpio, spi2
from misoc.targets.efc import BaseSoC
from misoc.integration.builder import builder_args, builder_argdict

from artiq.gateware.amp import AMPSoC
from artiq.gateware import rtio
from artiq.gateware.rtio.xilinx_clocking import fix_serdes_timing_path
from artiq.gateware.rtio.phy import ttl_simple
from artiq.gateware.rtio.phy import spi2 as rtio_spi
from artiq.gateware.drtio.transceiver import eem_serdes
from artiq.gateware.drtio.rx_synchronizer import NoRXSynchronizer
from artiq.gateware.drtio import *
from artiq.gateware.shuttler import Shuttler as Shuttler
from artiq.gateware.songbird import Songbird
from artiq.build_soc import *

ltc2000_pads = [
    ("ltc2000", 0,
        Subsignal("clk_p", Pins("fmc0:LA07_P"), IOStandard("LVDS_25")),
        Subsignal("clk_n", Pins("fmc0:LA07_N"), IOStandard("LVDS_25")),
        Subsignal("dcko_p", Pins("fmc0:LA01_CC_P"), IOStandard("LVDS_25")),
        Subsignal("dcko_n", Pins("fmc0:LA01_CC_N"), IOStandard("LVDS_25")),
        Subsignal("data_p", Pins(
            "fmc0:LA15_P fmc0:LA16_P fmc0:LA14_P",
            "fmc0:LA13_P fmc0:LA11_P fmc0:LA12_P",
            "fmc0:LA09_P fmc0:LA10_P fmc0:LA08_P",
            "fmc0:LA05_P fmc0:LA04_P fmc0:LA06_P",
            "fmc0:LA03_P fmc0:LA02_P fmc0:LA00_CC_P",
            "C18"), #H4, externally terminated on EFC, it's called fmc_clk_m2c !!!MAY NEED TO REMOVE R24 of FMC BOARD!!!
            IOStandard("LVDS_25")),
        Subsignal("data_n", Pins(
            "fmc0:LA15_N fmc0:LA16_N fmc0:LA14_N",
            "fmc0:LA13_N fmc0:LA11_N fmc0:LA12_N",
            "fmc0:LA09_N fmc0:LA10_N fmc0:LA08_N",
            "fmc0:LA05_N fmc0:LA04_N fmc0:LA06_N",
            "fmc0:LA03_N fmc0:LA02_N fmc0:LA00_CC_N",
            "C19"), #H5, externally terminated on EFC, it's called fmc_clk_m2c !!!MAY NEED TO REMOVE R24 of FMC BOARD!!!
            IOStandard("LVDS_25")),
        Subsignal("datb_p", Pins(
            "fmc0:LA32_P fmc0:LA33_P fmc0:LA30_P",
            "fmc0:LA31_P fmc0:LA28_P fmc0:LA29_P",
            "fmc0:LA24_P fmc0:LA25_P fmc0:LA26_P",
            "fmc0:LA27_P fmc0:LA21_P fmc0:LA22_P",
            "fmc0:LA23_P fmc0:LA19_P fmc0:LA20_P",
            "fmc0:LA17_CC_P"),
            IOStandard("LVDS_25")),
        Subsignal("datb_n", Pins(
            "fmc0:LA32_N fmc0:LA33_N fmc0:LA30_N",
            "fmc0:LA31_N fmc0:LA28_N fmc0:LA29_N",
            "fmc0:LA24_N fmc0:LA25_N fmc0:LA26_N",
            "fmc0:LA27_N fmc0:LA21_N fmc0:LA22_N",
            "fmc0:LA23_N fmc0:LA19_N fmc0:LA20_N",
            "fmc0:LA17_CC_N"),
            IOStandard("LVDS_25"))
    )
]

ltc2000_spi = [
    ("ltc2000_spi", 0,
        Subsignal("cs_n", Pins("fmc0:HA21_N"), IOStandard("LVCMOS25")),
        Subsignal("clk", Pins("fmc0:HA17_CC_P"), IOStandard("LVCMOS25")),
        Subsignal("mosi", Pins("fmc0:HA17_CC_N"), IOStandard("LVCMOS25")),
        Subsignal("miso", Pins("fmc0:HA21_P"), IOStandard("LVCMOS25"), Misc("PULLUP=TRUE"))
    )
]
shuttler_io = [
    ('dac_spi', 0,
        Subsignal('clk', Pins('fmc0:HB16_N')),
        Subsignal('mosi', Pins('fmc0:HB06_CC_N')),
        Subsignal('cs_n', Pins('fmc0:LA31_N fmc0:LA31_P fmc0:HB19_P fmc0:LA30_P')),
        IOStandard("LVCMOS18")),
    ('dac_rst', 0, Pins('fmc0:HB16_P'), IOStandard("LVCMOS18")),
    ('dac_din', 0,
        Subsignal('data', Pins('fmc0:HA06_N fmc0:HA06_P fmc0:HA07_N fmc0:HA02_N fmc0:HA07_P fmc0:HA02_P fmc0:HA03_N fmc0:HA03_P fmc0:HA04_N fmc0:HA04_P fmc0:HA05_N fmc0:HA05_P fmc0:HA00_CC_N fmc0:HA01_CC_N')),
        Subsignal('clk', Pins('fmc0:HA00_CC_P')),
        IOStandard('LVCMOS18')),
    ('dac_din', 1,
        Subsignal('data', Pins('fmc0:LA09_P fmc0:LA09_N fmc0:LA07_N fmc0:LA08_N fmc0:LA07_P fmc0:LA08_P fmc0:LA05_N fmc0:LA04_N fmc0:LA05_P fmc0:LA06_N fmc0:LA04_P fmc0:LA03_N fmc0:LA03_P fmc0:LA06_P')),
        Subsignal('clk', Pins('fmc0:LA00_CC_P')),
        IOStandard('LVCMOS18')),
    ('dac_din', 2,
        Subsignal('data', Pins('fmc0:HA14_N fmc0:HA14_P fmc0:HA12_N fmc0:HA12_P fmc0:HA13_N fmc0:HA10_N fmc0:HA10_P fmc0:HA11_N fmc0:HA11_P fmc0:HA13_P fmc0:HA08_N fmc0:HA08_P fmc0:HA09_N fmc0:HA09_P')),
        Subsignal('clk', Pins('fmc0:HA01_CC_P')),
        IOStandard('LVCMOS18')),
    ('dac_din', 3,
        Subsignal('data', Pins('fmc0:LA14_N fmc0:LA15_N fmc0:LA16_N fmc0:LA15_P fmc0:LA14_P fmc0:LA13_N fmc0:LA16_P fmc0:LA13_P fmc0:LA11_N fmc0:LA12_N fmc0:LA11_P fmc0:LA12_P fmc0:LA10_N fmc0:LA10_P')),
        Subsignal('clk', Pins('fmc0:LA01_CC_P')),
        IOStandard('LVCMOS18')),
    ('dac_din', 4,
        Subsignal('data', Pins('fmc0:HA22_N fmc0:HA19_N fmc0:HA22_P fmc0:HA21_N fmc0:HA21_P fmc0:HA19_P fmc0:HA18_CC_N fmc0:HA20_N fmc0:HA20_P fmc0:HA18_CC_P fmc0:HA15_N fmc0:HA15_P fmc0:HA16_N fmc0:HA16_P')),
        Subsignal('clk', Pins('fmc0:HA17_CC_P')),
        IOStandard('LVCMOS18')),
    ('dac_din', 5,
        Subsignal('data', Pins('fmc0:LA24_N fmc0:LA25_N fmc0:LA24_P fmc0:LA25_P fmc0:LA21_N fmc0:LA21_P fmc0:LA22_N fmc0:LA22_P fmc0:LA23_N fmc0:LA23_P fmc0:LA19_N fmc0:LA19_P fmc0:LA20_N fmc0:LA20_P')),
        Subsignal('clk', Pins('fmc0:LA17_CC_P')),
        IOStandard('LVCMOS18')),
    ('dac_din', 6,
        Subsignal('data', Pins('fmc0:HB08_N fmc0:HB08_P fmc0:HB07_N fmc0:HB07_P fmc0:HB04_N fmc0:HB04_P fmc0:HB01_N fmc0:HB05_N fmc0:HB01_P fmc0:HB05_P fmc0:HB02_N fmc0:HB02_P fmc0:HB03_N fmc0:HB03_P')),
        Subsignal('clk', Pins('fmc0:HB00_CC_P')),
        IOStandard('LVCMOS18')),
    ('dac_din', 7,
        Subsignal('data', Pins('fmc0:HB13_N fmc0:HB12_N fmc0:HB13_P fmc0:HB12_P fmc0:HB15_N fmc0:HB15_P fmc0:HB11_N fmc0:HB09_N fmc0:HB09_P fmc0:HB14_N fmc0:HB14_P fmc0:HB10_N fmc0:HB10_P fmc0:HB11_P')),
        Subsignal('clk', Pins('fmc0:HB06_CC_P')),
        IOStandard('LVCMOS18')),
    ('afe_ctrl_dir', 0, Pins('fmc0:LA26_N fmc0:HB00_CC_N fmc0:HB17_CC_P'), IOStandard("LVCMOS18")),
    ('afe_ctrl_oe_n', 0, Pins('fmc0:HB19_N'), IOStandard("LVCMOS18")),
    ('afe_relay', 0,
        Subsignal('clk', Pins('fmc0:LA02_N')),
        Subsignal('mosi', Pins('fmc0:LA00_CC_N')),
        Subsignal('cs_n', Pins('fmc0:LA02_P fmc0:LA01_CC_N')),
        IOStandard("LVCMOS18")),
    ('afe_adc_spi', 0,
        Subsignal('clk', Pins('fmc0:LA29_P')),
        Subsignal('mosi', Pins('fmc0:LA29_N')),
        Subsignal('miso', Pins('fmc0:LA30_N')),
        Subsignal('cs_n', Pins('fmc0:LA28_P')),
        IOStandard("LVCMOS18")),
    ('afe_adc_error_n', 0, Pins('fmc0:LA28_N'), IOStandard("LVCMOS18")),
]

class _SatelliteBase(BaseSoC, AMPSoC):
    mem_map = {
        "rtio":          0x20000000,
        "drtioaux":      0x50000000,
        "mailbox":       0x70000000
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, gateware_identifier_str=None, efc_hw_rev="v1.1", rtio_clk_freq=125e6, **kwargs):
        BaseSoC.__init__(self,
                 cpu_type="vexriscv",
                 hw_rev=efc_hw_rev,
                 cpu_bus_width=64,
                 sdram_controller_type="minicon",
                 l2_size=128*1024,
                 l2_line_size=64,
                 clk_freq=rtio_clk_freq,
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

        i2c = self.platform.request("fpga_i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1

        # Enable I2C
        i2c_reset = self.platform.request("i2c_mux_rst_n")
        self.comb += i2c_reset.eq(1)

        fix_serdes_timing_path(platform)

        self.config["DRTIO_ROLE"] = "satellite"
        self.config["RTIO_FREQUENCY"] = str(rtio_clk_freq/1e6)

        self.rtio_channels = []

        for i in range(2):
            phy = ttl_simple.Output(self.virtual_leds.get(i))
            self.submodules += phy
            self.rtio_channels.append(rtio.Channel.from_phy(phy))


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
            [self.drtiosat.cri, self.rtio_dma.cri],
            [self.local_io.cri],
            enable_routing=True)
        self.csr_devices.append("cri_con")
        self.submodules.routing_table = rtio.RoutingTableAccess(self.cri_con)
        self.csr_devices.append("routing_table")

        self.submodules.rtio_analyzer = rtio.Analyzer(self.rtio_tsc, self.local_io.cri,
                                                self.get_native_sdram_if(), cpu_dw=self.cpu_dw)
        self.csr_devices.append("rtio_analyzer")


class EfcShuttler(_SatelliteBase):
    def __init__(self, afe_hw_rev="v1.3", **kwargs):
        _SatelliteBase.__init__(self, **kwargs)
        platform = self.platform

        if afe_hw_rev in ("v1.0", "v1.1", "v1.2"):
            afe_adc_io = ('afe_adc_spi', 0,
                            Subsignal('clk', Pins('fmc0:LA29_P')),
                            Subsignal('mosi', Pins('fmc0:LA29_N')),
                            Subsignal('miso', Pins('fmc0:LA30_N')),
                            Subsignal('cs_n', Pins('fmc0:LA28_P')),
                            IOStandard("LVCMOS18"))
        elif afe_hw_rev == "v1.3":
            afe_adc_io = ('afe_adc_spi', 0,
                        Subsignal('clk', Pins('fmc0:LA29_N')),
                        Subsignal('mosi', Pins('fmc0:LA28_P')),
                        Subsignal('miso', Pins('fmc0:LA30_N')),
                        Subsignal('cs_n', Pins('fmc0:LA29_P')),
                        IOStandard("LVCMOS18"))
        else:
            raise ValueError("Unknown AFE hardware revision", afe_hw_rev)
        shuttler_io.append(afe_adc_io)

        platform.add_extension(shuttler_io)

        self.submodules.shuttler = Shuttler([platform.request("dac_din", i) for i in range(8)])
        self.csr_devices.append("shuttler")
        self.rtio_channels.extend(rtio.Channel.from_phy(phy) for phy in self.shuttler.phys)

        afe_dir = platform.request("afe_ctrl_dir")
        self.comb += afe_dir.eq(0b011)

        afe_oe = platform.request("afe_ctrl_oe_n")
        self.comb += afe_oe.eq(0)

        relay_led_phy = rtio_spi.SPIMaster(self.platform.request("afe_relay"))
        self.submodules += relay_led_phy
        print("SHUTTLER RELAY at RTIO channel 0x{:06x}".format(len(self.rtio_channels)))
        self.rtio_channels.append(rtio.Channel.from_phy(relay_led_phy))

        adc_error_n = platform.request("afe_adc_error_n")
        self.comb += adc_error_n.eq(1)

        adc_spi = rtio_spi.SPIMaster(self.platform.request("afe_adc_spi"))
        self.submodules += adc_spi
        print("SHUTTLER ADC at RTIO channel 0x{:06x}".format(len(self.rtio_channels)))
        self.rtio_channels.append(rtio.Channel.from_phy(adc_spi))

        self.submodules.converter_spi = spi2.SPIMaster(spi2.SPIInterface(self.platform.request("dac_spi", 0)))
        self.csr_devices.append("converter_spi")

        self.submodules.dac_rst = gpio.GPIOOut(self.platform.request("dac_rst"))
        self.csr_devices.append("dac_rst")

        self.add_rtio(self.rtio_channels)


class EfcSongbird(_SatelliteBase):
    def __init__(self, **kwargs):
        _SatelliteBase.__init__(self, **kwargs)

        platform = self.platform
        rtio_clk_freq = kwargs["rtio_clk_freq"]

        platform.add_extension(ltc2000_spi)
        ltc2000_spi_phy = rtio_spi.SPIMaster(self.platform.request("ltc2000_spi", 0))
        self.submodules += ltc2000_spi_phy
        print("Songbird LTC2000 DAC SPI at RTIO channel 0x{:06x}".format(len(self.rtio_channels)))
        self.rtio_channels.append(rtio.Channel.from_phy(ltc2000_spi_phy))

        self.submodules.songbird = Songbird(self.platform, ltc2000_pads, rtio_clk_freq)

        for phy in self.songbird.phys:
            print("Songbird LTC2000 {} at RTIO channel 0x{:06x}".format(phy.name, len(self.rtio_channels)))
            self.rtio_channels.append(rtio.Channel.from_phy(phy))

        self.clock_domains.cd_dds200 = ClockDomain()
        self.clock_domains.cd_dds600 = ClockDomain(reset_less=True)

        mmcm_fb_in = Signal()
        mmcm_fb_out = Signal()
        mmcm_dds200 = Signal()
        mmcm_dds600 = Signal()
        mmcm_locked = Signal()
        mmcm_reset = Signal()

        self.comb += [
            self.songbird.mmcm_locked.eq(mmcm_locked),
            mmcm_reset.eq(self.songbird.reset.i),
        ]

        clk_mult = 12 if rtio_clk_freq == 100e6 else 10
        self.specials += [
            Instance("MMCME2_BASE",
                p_CLKIN1_PERIOD=1e9/rtio_clk_freq,
                i_CLKIN1=ClockSignal(),

                i_RST=ResetSignal() | mmcm_reset,

                i_CLKFBIN=mmcm_fb_in,
                o_CLKFBOUT=mmcm_fb_out,
                o_LOCKED=mmcm_locked,

                # VCO @ 1.2/1.25 with MULT=12/10
                p_CLKFBOUT_MULT_F=clk_mult, p_DIVCLK_DIVIDE=1,

                # 600/625MHz
                p_CLKOUT0_DIVIDE_F=2, p_CLKOUT0_PHASE=0.0, o_CLKOUT0=mmcm_dds600,

                # 200/208.33MHz
                p_CLKOUT1_DIVIDE=6, p_CLKOUT1_PHASE=0.0, o_CLKOUT1=mmcm_dds200,

            ),
            Instance("BUFG", i_I=mmcm_dds200, o_O=self.cd_dds200.clk),
            Instance("BUFG", i_I=mmcm_dds600, o_O=self.cd_dds600.clk),
            Instance("BUFG", i_I=mmcm_fb_out, o_O=mmcm_fb_in),
            AsyncResetSynchronizer(self.cd_dds200, ~mmcm_locked)
        ]
        platform.add_false_path_constraints(self.crg.cd_sys.clk, self.cd_dds200.clk)

        self.add_rtio(self.rtio_channels)

VARIANTS = {"shuttler": EfcShuttler, "songbird": EfcSongbird}

def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder for EEM FMC Carrier systems")
    builder_args(parser)
    parser.set_defaults(output_dir="artiq_efc")
    parser.add_argument("--efc-hw-rev", choices=["v1.0", "v1.1"], default="v1.1",
                        help="EFC hardware revision")
    parser.add_argument("--gateware-identifier-str", default=None,
                        help="Override ROM identifier")
    parser.add_argument("--drtio100mhz", action="store_true",
                        help="Set RTIO clock frequency to 100 MHz (default is 125 MHz)")

    subparsers = parser.add_subparsers(dest="variant", help="Variant to build", required=True)

    parser_shuttler = subparsers.add_parser("shuttler", help="Build Shuttler variant")
    parser_shuttler.add_argument("--afe-hw-rev", choices=["v1.0", "v1.1", "v1.2", "v1.3"],
                                 default="v1.3", help="AFE hardware revision")

    subparsers.add_parser("songbird", help="Build Songbird variant")

    args = parser.parse_args()

    argdict = dict()
    argdict["gateware_identifier_str"] = args.gateware_identifier_str
    argdict["efc_hw_rev"] = args.efc_hw_rev
    if args.variant == "shuttler":
        argdict["afe_hw_rev"] = args.afe_hw_rev
    argdict["rtio_clk_freq"] = 100e6 if args.drtio100mhz else 125e6
    variant = args.variant.lower()

    cls = VARIANTS[variant]
    soc = cls(**argdict)
    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
