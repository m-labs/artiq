#!/usr/bin/env python3

import argparse

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.cdc import MultiReg
from migen.genlib.io import DifferentialOutput

from misoc.interconnect.csr import *
from misoc.cores import gpio
from misoc.cores.a7_gtp import *
from misoc.targets.kasli import (
    BaseSoC, MiniSoC, soc_kasli_args, soc_kasli_argdict)
from misoc.integration.builder import builder_args, builder_argdict

from artiq.gateware.amp import AMPSoC
from artiq.gateware import rtio
from artiq.gateware.rtio.phy import ttl_simple, ttl_serdes_7series, edge_counter
from artiq.gateware.rtio.xilinx_clocking import fix_serdes_timing_path
from artiq.gateware import eem
from artiq.gateware.drtio.transceiver import gtp_7series
from artiq.gateware.drtio.siphaser import SiPhaser7Series
from artiq.gateware.drtio.rx_synchronizer import XilinxRXSynchronizer
from artiq.gateware.drtio import *
from artiq.build_soc import *


class SMAClkinForward(Module):
    def __init__(self, platform):
        sma_clkin = platform.request("sma_clkin")
        sma_clkin_se = Signal()
        sma_clkin_buffered = Signal()
        cdr_clk_se = Signal()
        cdr_clk = platform.request("cdr_clk")
        self.specials += [
            Instance("IBUFDS", i_I=sma_clkin.p, i_IB=sma_clkin.n, o_O=sma_clkin_se),
            Instance("BUFIO", i_I=sma_clkin_se, o_O=sma_clkin_buffered),
            Instance("ODDR", i_C=sma_clkin_buffered, i_CE=1, i_D1=0, i_D2=1, o_Q=cdr_clk_se),
            Instance("OBUFDS", i_I=cdr_clk_se, o_O=cdr_clk.p, o_OB=cdr_clk.n)
        ]


class StandaloneBase(MiniSoC, AMPSoC):
    mem_map = {
        "cri_con":       0x10000000,
        "rtio":          0x20000000,
        "rtio_dma":      0x30000000,
        "mailbox":       0x70000000
    }
    mem_map.update(MiniSoC.mem_map)

    def __init__(self, gateware_identifier_str=None, hw_rev="v2.0", **kwargs):
        if hw_rev in ("v1.0", "v1.1"):
            cpu_bus_width = 32
        else:
            cpu_bus_width = 64
        MiniSoC.__init__(self,
                         cpu_type="vexriscv",
                         hw_rev=hw_rev,
                         cpu_bus_width=cpu_bus_width,
                         sdram_controller_type="minicon",
                         l2_size=128*1024,
                         integrated_sram_size=8192,
                         ethmac_nrxslots=4,
                         ethmac_ntxslots=4,
                         clk_freq=kwargs.get("rtio_frequency", 125.0e6),
                         rtio_sys_merge=True,
                         **kwargs)
        AMPSoC.__init__(self)
        add_identifier(self, gateware_identifier_str=gateware_identifier_str)

        if self.platform.hw_rev == "v2.0":
            self.submodules.error_led = gpio.GPIOOut(Cat(
                self.platform.request("error_led")))
            self.csr_devices.append("error_led")
            self.submodules += SMAClkinForward(self.platform)
            cdr_clk_out = self.platform.request("cdr_clk_clean")
        else:
            cdr_clk_out = self.platform.request("si5324_clkout")
        
        cdr_clk = Signal()
        cdr_clk_buf = Signal()
        self.platform.add_period_constraint(cdr_clk_out, 8.)

        self.specials += [
            Instance("IBUFDS_GTE2",
                i_CEB=0,
                i_I=cdr_clk_out.p, i_IB=cdr_clk_out.n,
                o_O=cdr_clk,
                p_CLKCM_CFG="TRUE",
                p_CLKRCV_TRST="TRUE", 
                p_CLKSWING_CFG=3), 
            Instance("BUFG", i_I=cdr_clk, o_O=cdr_clk_buf)
        ]

        self.crg.configure(cdr_clk_buf)

        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1
        self.config["HAS_SI5324"] = None
        self.config["SI5324_SOFT_RESET"] = None

    def add_rtio(self, rtio_channels, sed_lanes=8):
        fix_serdes_timing_path(self.platform)
        self.submodules.rtio_tsc = rtio.TSC(glbl_fine_ts_width=3)
        self.submodules.rtio_core = rtio.Core(self.rtio_tsc, rtio_channels, lane_count=sed_lanes)
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


class Tester(StandaloneBase):
    """
    Configuration for CI tests. Contains the maximum number of different EEMs.
    """
    def __init__(self, hw_rev=None, dds=None, **kwargs):
        if hw_rev is None:
            hw_rev = "v2.0"
        if dds is None:
            dds = "ad9910"
        StandaloneBase.__init__(self, hw_rev=hw_rev, **kwargs)

        # self.config["SI5324_EXT_REF"] = None
        self.config["RTIO_FREQUENCY"] = "125.0"
        if hw_rev == "v1.0":
            # EEM clock fan-out from Si5324, not MMCX
            self.comb += self.platform.request("clk_sel").eq(1)

        self.rtio_channels = []
        eem.DIO.add_std(self, 5,
            ttl_serdes_7series.InOut_8X, ttl_serdes_7series.Output_8X,
            edge_counter_cls=edge_counter.SimpleEdgeCounter)
        eem.Urukul.add_std(self, 0, 1, ttl_serdes_7series.Output_8X, dds,
                           ttl_simple.ClockGen)
        eem.Sampler.add_std(self, 3, 2, ttl_serdes_7series.Output_8X)
        eem.Zotino.add_std(self, 4, ttl_serdes_7series.Output_8X)

        if hw_rev in ("v1.0", "v1.1"):
            for i in (1, 2):
                sfp_ctl = self.platform.request("sfp_ctl", i)
                phy = ttl_simple.Output(sfp_ctl.led)
                self.submodules += phy
                self.rtio_channels.append(rtio.Channel.from_phy(phy))

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(self.rtio_channels)
        self.rtio_channels.append(rtio.LogChannel())
        self.add_rtio(self.rtio_channels)


class SUServo(StandaloneBase):
    """
    SUServo (Sampler-Urukul-Servo) extension variant configuration
    """
    def __init__(self, hw_rev=None, **kwargs):
        if hw_rev is None:
            hw_rev = "v2.0"
        StandaloneBase.__init__(self, hw_rev=hw_rev, **kwargs)

        # self.config["SI5324_EXT_REF"] = None
        self.config["RTIO_FREQUENCY"] = "125.0"
        if hw_rev == "v1.0":
            # EEM clock fan-out from Si5324, not MMCX
            self.comb += self.platform.request("clk_sel").eq(1)

        self.rtio_channels = []
        # EEM0, EEM1: DIO
        eem.DIO.add_std(self, 0,
            ttl_serdes_7series.InOut_8X, ttl_serdes_7series.Output_8X)
        eem.DIO.add_std(self, 1,
            ttl_serdes_7series.Output_8X, ttl_serdes_7series.Output_8X)

        # EEM3/2: Sampler, EEM5/4: Urukul, EEM7/6: Urukul
        eem.SUServo.add_std(self, 
                            eems_sampler=(3, 2), 
                            eems_urukul=[[5, 4], [7, 6]])

        for i in (1, 2):
            sfp_ctl = self.platform.request("sfp_ctl", i)
            phy = ttl_simple.Output(sfp_ctl.led)
            self.submodules += phy
            self.rtio_channels.append(rtio.Channel.from_phy(phy))

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(self.rtio_channels)
        self.rtio_channels.append(rtio.LogChannel())

        self.add_rtio(self.rtio_channels)

        pads = self.platform.lookup_request("sampler3_adc_data_p")
        self.platform.add_false_path_constraints(
            pads.clkout, self.crg.cd_sys.clk)


class MasterBase(MiniSoC, AMPSoC):
    mem_map = {
        "cri_con":       0x10000000,
        "rtio":          0x20000000,
        "rtio_dma":      0x30000000,
        "drtioaux":      0x50000000,
        "mailbox":       0x70000000
    }
    mem_map.update(MiniSoC.mem_map)

    def __init__(self, rtio_clk_freq=125e6, enable_sata=False, gateware_identifier_str=None, hw_rev="v2.0", **kwargs):
        if hw_rev in ("v1.0", "v1.1"):
            cpu_bus_width = 32
        else:
            cpu_bus_width = 64
        MiniSoC.__init__(self,
                         cpu_type="vexriscv",
                         hw_rev=hw_rev,
                         cpu_bus_width=cpu_bus_width,
                         sdram_controller_type="minicon",
                         l2_size=128*1024,
                         integrated_sram_size=8192,
                         ethmac_nrxslots=4,
                         ethmac_ntxslots=4,
                         clk_freq=rtio_clk_freq,
                         rtio_sys_merge=True,
                         **kwargs)
        AMPSoC.__init__(self)
        add_identifier(self, gateware_identifier_str=gateware_identifier_str)

        platform = self.platform

        if platform.hw_rev == "v2.0":
            self.submodules.error_led = gpio.GPIOOut(Cat(
                self.platform.request("error_led")))
            self.csr_devices.append("error_led")
            self.submodules += SMAClkinForward(platform)

        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1
        self.config["HAS_SI5324"] = None
        self.config["SI5324_SOFT_RESET"] = None
        self.config["RTIO_FREQUENCY"] = str(rtio_clk_freq/1e6)

        drtio_data_pads = []
        if enable_sata:
            drtio_data_pads.append(platform.request("sata"))
        drtio_data_pads += [platform.request("sfp", i) for i in range(1, 3)]
        if self.platform.hw_rev == "v2.0":
            drtio_data_pads.append(platform.request("sfp", 3))

        if self.platform.hw_rev in ("v1.0", "v1.1"):
            sfp_ctls = [platform.request("sfp_ctl", i) for i in range(1, 3)]
            self.comb += [sc.tx_disable.eq(0) for sc in sfp_ctls]

        self.submodules.drtio_transceiver = gtp_7series.GTP(
            qpll_channel=self.drtio_qpll_channel,
            data_pads=drtio_data_pads,
            sys_clk_freq=self.clk_freq,
            rtio_clk_freq=rtio_clk_freq)
        self.csr_devices.append("drtio_transceiver")

        if enable_sata:
            sfp_channels = self.drtio_transceiver.channels[1:]
        else:
            sfp_channels = self.drtio_transceiver.channels
        if self.platform.hw_rev in ("v1.0", "v1.1"):
            self.comb += [sfp_ctl.led.eq(channel.rx_ready)
                for sfp_ctl, channel in zip(sfp_ctls, sfp_channels)]
        if self.platform.hw_rev == "v2.0":
            self.comb += [self.virtual_leds.get(i + 1).eq(channel.rx_ready)
                          for i, channel in enumerate(sfp_channels)]

        self.submodules.rtio_tsc = rtio.TSC(glbl_fine_ts_width=3)

        drtio_csr_group = []
        drtioaux_csr_group = []
        drtioaux_memory_group = []
        self.drtio_cri = []
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
            self.drtio_cri.append(core.cri)
            self.csr_devices.append(core_name)

            coreaux = cdr(DRTIOAuxController(core.link_layer, self.cpu_dw))
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
        gtp = self.drtio_transceiver.gtps[0]

        txout_buf = Signal()
        self.specials += Instance("BUFG", i_I=gtp.txoutclk, o_O=txout_buf)
        self.crg.configure(txout_buf, clk_sw=gtp.tx_init.done)

        platform.add_period_constraint(gtp.txoutclk, rtio_clk_period)
        platform.add_period_constraint(gtp.rxoutclk, rtio_clk_period)

        platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            gtp.txoutclk, gtp.rxoutclk)
        for gtp in self.drtio_transceiver.gtps[1:]:
            platform.add_period_constraint(gtp.rxoutclk, rtio_clk_period)
            platform.add_false_path_constraints(
                self.crg.cd_sys.clk, gtp.rxoutclk)

        fix_serdes_timing_path(platform)

    def add_rtio(self, rtio_channels, sed_lanes=8):
        # Only add MonInj core if there is anything to monitor
        if any([len(c.probes) for c in rtio_channels]):
            self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)
            self.csr_devices.append("rtio_moninj")

        self.submodules.rtio_core = rtio.Core(self.rtio_tsc, rtio_channels, lane_count=sed_lanes)
        self.csr_devices.append("rtio_core")

        self.submodules.rtio = rtio.KernelInitiator(self.rtio_tsc)
        self.submodules.rtio_dma = ClockDomainsRenamer("sys_kernel")(
            rtio.DMA(self.get_native_sdram_if(), self.cpu_dw))
        self.register_kernel_cpu_csrdevice("rtio")
        self.register_kernel_cpu_csrdevice("rtio_dma")
        self.submodules.cri_con = rtio.CRIInterconnectShared(
            [self.rtio.cri, self.rtio_dma.cri],
            [self.rtio_core.cri] + self.drtio_cri,
            enable_routing=True)
        self.register_kernel_cpu_csrdevice("cri_con")
        self.submodules.routing_table = rtio.RoutingTableAccess(self.cri_con)
        self.csr_devices.append("routing_table")

        self.submodules.rtio_analyzer = rtio.Analyzer(self.rtio_tsc, self.rtio_core.cri,
                                                      self.get_native_sdram_if(), cpu_dw=self.cpu_dw)
        self.csr_devices.append("rtio_analyzer")

    # Never running out of stupid features, GTs on A7 make you pack
    # unrelated transceiver PLLs into one GTPE2_COMMON yourself.
    def create_qpll(self):
        if self.platform.hw_rev == "v2.0":
            cdr_clk_out = self.platform.request("cdr_clk_clean")
        else:
            cdr_clk_out = self.platform.request("si5324_clkout")
        
        cdr_clk = Signal()
        self.platform.add_period_constraint(cdr_clk_out, 8.)

        self.specials += Instance("IBUFDS_GTE2",
            i_CEB=0,
            i_I=cdr_clk_out.p, i_IB=cdr_clk_out.n,
            o_O=cdr_clk,
            p_CLKCM_CFG="TRUE",
            p_CLKRCV_TRST="TRUE", 
            p_CLKSWING_CFG=3)
        # Note precisely the rules Xilinx made up:
        # refclksel=0b001 GTREFCLK0 selected
        # refclksel=0b010 GTREFCLK1 selected
        # but if only one clock is used, then it must be 001.
        qpll_drtio_settings = QPLLSettings(
            refclksel=0b001,
            fbdiv=4,
            fbdiv_45=5,
            refclk_div=1)
        qpll_eth_settings = QPLLSettings(
            refclksel=0b010,
            fbdiv=4,
            fbdiv_45=5,
            refclk_div=1)

        qpll = QPLL(cdr_clk, qpll_drtio_settings,
                    self.crg.clk125_buf, qpll_eth_settings)
        self.submodules += qpll
        self.drtio_qpll_channel, self.ethphy_qpll_channel = qpll.channels


class SatelliteBase(MiniSoC, AMPSoC):
    mem_map = {
        "rtio":          0x20000000,
        "drtioaux":      0x50000000,
        "mailbox":       0x70000000
    }
    mem_map.update(MiniSoC.mem_map)

    def __init__(self, rtio_clk_freq=125e6, enable_sata=False, *, gateware_identifier_str=None, hw_rev="v2.0", **kwargs):
        if hw_rev in ("v1.0", "v1.1"):
            cpu_bus_width = 32
        else:
            cpu_bus_width = 64

        MiniSoC.__init__(self,
                 cpu_type="vexriscv",
                 hw_rev=hw_rev,
                 cpu_bus_width=cpu_bus_width,
                 sdram_controller_type="minicon",
                 l2_size=128*1024,
                 integrated_sram_size=8192,
                 ethmac_nrxslots=4,
                 ethmac_ntxslots=4,
                 clk_freq=rtio_clk_freq,
                 rtio_sys_merge=True,
                 **kwargs)
        AMPSoC.__init__(self)
        add_identifier(self, gateware_identifier_str=gateware_identifier_str)

        platform = self.platform

        if self.platform.hw_rev == "v2.0":
            self.submodules.error_led = gpio.GPIOOut(Cat(
                self.platform.request("error_led")))
            self.csr_devices.append("error_led")

        drtio_data_pads = []
        if enable_sata:
            drtio_data_pads.append(platform.request("sata"))
        drtio_data_pads += [platform.request("sfp", i) for i in range(1, 3)]
        if self.platform.hw_rev == "v2.0":
            drtio_data_pads.append(platform.request("sfp", 3))

        if self.platform.hw_rev in ("v1.0", "v1.1"):
            sfp_ctls = [platform.request("sfp_ctl", i) for i in range(1, 3)]
            self.comb += [sc.tx_disable.eq(0) for sc in sfp_ctls]
        self.submodules.drtio_transceiver = gtp_7series.GTP(
            qpll_channel=self.drtio_qpll_channel,
            data_pads=drtio_data_pads,
            sys_clk_freq=self.clk_freq,
            rtio_clk_freq=rtio_clk_freq)
        self.csr_devices.append("drtio_transceiver")

        if enable_sata:
            sfp_channels = self.drtio_transceiver.channels[1:]
        else:
            sfp_channels = self.drtio_transceiver.channels
        if self.platform.hw_rev in ("v1.0", "v1.1"):
            self.comb += [sfp_ctl.led.eq(channel.rx_ready)
                for sfp_ctl, channel in zip(sfp_ctls, sfp_channels)]
        if self.platform.hw_rev == "v2.0":
            self.comb += [self.virtual_leds.get(i).eq(channel.rx_ready)
                          for i, channel in enumerate(sfp_channels)]

        self.submodules.rtio_tsc = rtio.TSC(glbl_fine_ts_width=3)

        drtioaux_csr_group = []
        drtioaux_memory_group = []
        drtiorep_csr_group = []
        self.drtio_cri = []
        for i in range(len(self.drtio_transceiver.channels)):
            coreaux_name = "drtioaux" + str(i)
            memory_name = "drtioaux" + str(i) + "_mem"
            drtioaux_csr_group.append(coreaux_name)
            drtioaux_memory_group.append(memory_name)

            cdr = ClockDomainsRenamer({"rtio_rx": "rtio_rx" + str(i)})

            if i == 0:
                self.submodules.rx_synchronizer = cdr(XilinxRXSynchronizer())
                core = cdr(DRTIOSatellite(
                    self.rtio_tsc, self.drtio_transceiver.channels[i],
                    self.rx_synchronizer))
                self.submodules.drtiosat = core
                self.csr_devices.append("drtiosat")
            else:
                corerep_name = "drtiorep" + str(i-1)
                drtiorep_csr_group.append(corerep_name)

                core = cdr(DRTIORepeater(
                    self.rtio_tsc, self.drtio_transceiver.channels[i]))
                setattr(self.submodules, corerep_name, core)
                self.drtio_cri.append(core.cri)
                self.csr_devices.append(corerep_name)

            coreaux = cdr(DRTIOAuxController(core.link_layer, self.cpu_dw))
            setattr(self.submodules, coreaux_name, coreaux)
            self.csr_devices.append(coreaux_name)

            memory_address = self.mem_map["drtioaux"] + 0x800*i
            self.add_wb_slave(memory_address, 0x800,
                              coreaux.bus)
            self.add_memory_region(memory_name, memory_address | self.shadow_base, 0x800)
        self.config["HAS_DRTIO"] = None
        self.config["HAS_DRTIO_ROUTING"] = None
        self.add_csr_group("drtioaux", drtioaux_csr_group)
        self.add_memory_group("drtioaux_mem", drtioaux_memory_group)
        self.add_csr_group("drtiorep", drtiorep_csr_group)

        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1

        rtio_clk_period = 1e9/rtio_clk_freq
        self.config["RTIO_FREQUENCY"] = str(rtio_clk_freq/1e6)

        self.submodules.siphaser = SiPhaser7Series(
            si5324_clkin=platform.request("cdr_clk") if platform.hw_rev == "v2.0"
                else platform.request("si5324_clkin"),
            rx_synchronizer=self.rx_synchronizer,
            ref_clk=self.crg.clk125_div2, ref_div2=True,
            rtio_clk_freq=rtio_clk_freq)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk, self.siphaser.mmcm_freerun_output)
        self.csr_devices.append("siphaser")
        self.config["HAS_SI5324"] = None
        self.config["SI5324_SOFT_RESET"] = None

        gtp = self.drtio_transceiver.gtps[0]
        txout_buf = Signal()
        self.specials += Instance("BUFG", i_I=gtp.txoutclk, o_O=txout_buf)
        self.crg.configure(txout_buf, clk_sw=gtp.tx_init.done)

        platform.add_period_constraint(gtp.txoutclk, rtio_clk_period)
        platform.add_period_constraint(gtp.rxoutclk, rtio_clk_period)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            gtp.txoutclk, gtp.rxoutclk)
        for gtp in self.drtio_transceiver.gtps[1:]:
            platform.add_period_constraint(gtp.rxoutclk, rtio_clk_period)
            platform.add_false_path_constraints(
                self.crg.cd_sys.clk, gtp.rxoutclk)

        fix_serdes_timing_path(platform)

    def add_rtio(self, rtio_channels, sed_lanes=8):
        # Only add MonInj core if there is anything to monitor
        if any([len(c.probes) for c in rtio_channels]):
            self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)
            self.csr_devices.append("rtio_moninj")

        # satellite (master-controlled) RTIO
        self.submodules.local_io = SyncRTIO(self.rtio_tsc, rtio_channels, lane_count=sed_lanes)
        self.comb += self.drtiosat.async_errors.eq(self.local_io.async_errors)

        # sub kernel RTIO
        self.submodules.rtio = rtio.KernelInitiator(self.rtio_tsc)
        self.register_kernel_cpu_csrdevice("rtio")

        self.submodules.rtio_dma = rtio.DMA(self.get_native_sdram_if(), self.cpu_dw)
        self.csr_devices.append("rtio_dma")
        # remember to switch cricon to 2 when running kernels
        self.submodules.cri_con = rtio.CRIInterconnectShared(
            [self.drtiosat.cri, self.rtio_dma.cri, self.rtio.cri],
            [self.local_io.cri] + self.drtio_cri,
            enable_routing=True)
        self.csr_devices.append("cri_con")
        self.submodules.routing_table = rtio.RoutingTableAccess(self.cri_con)
        self.csr_devices.append("routing_table")
        
        self.submodules.rtio_analyzer = rtio.Analyzer(self.rtio_tsc, self.local_io.cri,
                                                self.get_native_sdram_if(), cpu_dw=self.cpu_dw)
        self.csr_devices.append("rtio_analyzer")


    def create_qpll(self):
        if self.platform.hw_rev == "v2.0":
            cdr_clk_out = self.platform.request("cdr_clk_clean")
        else:
            cdr_clk_out = self.platform.request("si5324_clkout")
        
        cdr_clk = Signal()
        self.platform.add_period_constraint(cdr_clk_out, 8.)

        self.specials += Instance("IBUFDS_GTE2",
            i_CEB=0,
            i_I=cdr_clk_out.p, i_IB=cdr_clk_out.n,
            o_O=cdr_clk,
            p_CLKCM_CFG="TRUE",
            p_CLKRCV_TRST="TRUE", 
            p_CLKSWING_CFG=3)
        # Note precisely the rules Xilinx made up:
        # refclksel=0b001 GTREFCLK0 selected
        # refclksel=0b010 GTREFCLK1 selected
        # but if only one clock is used, then it must be 001.
        qpll_drtio_settings = QPLLSettings(
            refclksel=0b001,
            fbdiv=4,
            fbdiv_45=5,
            refclk_div=1)
        qpll_eth_settings = QPLLSettings(
            refclksel=0b010,
            fbdiv=4,
            fbdiv_45=5,
            refclk_div=1)

        qpll = QPLL(cdr_clk, qpll_drtio_settings,
                    self.crg.clk125_buf, qpll_eth_settings)
        self.submodules += qpll
        self.drtio_qpll_channel, self.ethphy_qpll_channel = qpll.channels


class Master(MasterBase):
    def __init__(self, hw_rev=None, **kwargs):
        if hw_rev is None:
            hw_rev = "v2.0"
        MasterBase.__init__(self, hw_rev=hw_rev, **kwargs)

        self.rtio_channels = []

        phy = ttl_simple.Output(self.platform.request("user_led", 0))
        self.submodules += phy
        self.rtio_channels.append(rtio.Channel.from_phy(phy))
        # matches Tester EEM numbers
        eem.DIO.add_std(self, 5,
            ttl_serdes_7series.InOut_8X, ttl_serdes_7series.Output_8X)
        eem.Urukul.add_std(self, 0, 1, ttl_serdes_7series.Output_8X)

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(self.rtio_channels)
        self.rtio_channels.append(rtio.LogChannel())

        self.add_rtio(self.rtio_channels)


class Satellite(SatelliteBase):
    def __init__(self, hw_rev=None, **kwargs):
        if hw_rev is None:
            hw_rev = "v2.0"
        SatelliteBase.__init__(self, hw_rev=hw_rev, **kwargs)

        self.rtio_channels = []
        phy = ttl_simple.Output(self.platform.request("user_led", 0))
        self.submodules += phy
        self.rtio_channels.append(rtio.Channel.from_phy(phy))
        # matches Tester EEM numbers
        eem.DIO.add_std(self, 5,
            ttl_serdes_7series.InOut_8X, ttl_serdes_7series.Output_8X)

        self.add_rtio(self.rtio_channels)


VARIANTS = {cls.__name__.lower(): cls for cls in [Tester, SUServo, Master, Satellite]}


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder for Kasli systems")
    builder_args(parser)
    soc_kasli_args(parser)
    parser.set_defaults(output_dir="artiq_kasli")
    parser.add_argument("-V", "--variant", default="tester",
                        help="variant: {} (default: %(default)s)".format(
                            "/".join(sorted(VARIANTS.keys()))))
    parser.add_argument("--tester-dds", default=None,
                        help="Tester variant DDS type: ad9910/ad9912 "
                             "(default: ad9910)")
    parser.add_argument("--gateware-identifier-str", default=None,
                        help="Override ROM identifier")
    args = parser.parse_args()

    argdict = dict()
    argdict["gateware_identifier_str"] = args.gateware_identifier_str
    argdict["dds"] = args.tester_dds

    variant = args.variant.lower()
    try:
        cls = VARIANTS[variant]
    except KeyError:
        raise SystemExit("Invalid variant (-V/--variant)")

    soc = cls(**soc_kasli_argdict(args), **argdict)
    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
