#!/usr/bin/env python3

import argparse
import logging
from packaging.version import Version

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

from artiq import __version__ as artiq_version
from artiq.gateware.amp import AMPSoC
from artiq.gateware import rtio
from artiq.gateware.rtio.phy import ttl_simple, ttl_serdes_7series, edge_counter
from artiq.gateware.rtio.xilinx_clocking import fix_serdes_timing_path
from artiq.gateware import rtio, eem, eem_7series
from artiq.gateware.drtio.transceiver import gtp_7series, eem_serdes
from artiq.gateware.drtio.siphaser import SiPhaser7Series
from artiq.gateware.drtio.rx_synchronizer import XilinxRXSynchronizer
from artiq.gateware.drtio import *
from artiq.gateware.wrpll import wrpll
from artiq.build_soc import *
from artiq.coredevice import jsondesc

logger = logging.getLogger(__name__)


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

    def __init__(self, gateware_identifier_str=None, with_wrpll=False, hw_rev="v2.0", **kwargs):
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

        self.config["DRTIO_ROLE"] = "standalone"

        if self.platform.hw_rev == "v2.0":
            self.submodules.error_led = gpio.GPIOOut(Cat(
                self.platform.request("error_led")))
            self.csr_devices.append("error_led")
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

        if with_wrpll:
            clk_synth = self.platform.request("cdr_clk_clean_fabric")
            clk_synth_se = Signal()
            self.platform.add_period_constraint(clk_synth.p, 8.0)
            self.specials += Instance("IBUFGDS", p_DIFF_TERM="TRUE", p_IBUF_LOW_PWR="FALSE", i_I=clk_synth.p, i_IB=clk_synth.n, o_O=clk_synth_se)
            self.submodules.wrpll_refclk = wrpll.FrequencyMultiplier(self.platform.request("sma_clkin"))
            self.submodules.wrpll = wrpll.WRPLL(
                platform=self.platform,
                cd_ref=self.wrpll_refclk.cd_ref,
                main_clk_se=clk_synth_se)
            self.csr_devices.append("wrpll_refclk")
            self.csr_devices.append("wrpll")
            self.interrupt_devices.append("wrpll")
            self.config["HAS_SI549"] = None
            self.config["WRPLL_REF_CLK"] = "SMA_CLKIN"
        else:
            if self.platform.hw_rev == "v2.0":
                self.submodules += SMAClkinForward(self.platform)
            self.config["HAS_SI5324"] = None
            self.config["SI5324_SOFT_RESET"] = None

        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1

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


class MasterBase(MiniSoC, AMPSoC):
    mem_map = {
        "cri_con":       0x10000000,
        "rtio":          0x20000000,
        "rtio_dma":      0x30000000,
        "drtioaux":      0x50000000,
        "mailbox":       0x70000000
    }
    mem_map.update(MiniSoC.mem_map)

    def __init__(self, rtio_clk_freq=125e6, enable_sata=False, with_wrpll=False, gateware_identifier_str=None, hw_rev="v2.0", **kwargs):
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

        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1

        if with_wrpll:
            clk_synth = platform.request("cdr_clk_clean_fabric")
            clk_synth_se = Signal()
            platform.add_period_constraint(clk_synth.p, 8.0)
            self.specials += Instance("IBUFGDS", p_DIFF_TERM="TRUE", p_IBUF_LOW_PWR="FALSE", i_I=clk_synth.p, i_IB=clk_synth.n, o_O=clk_synth_se)
            self.submodules.wrpll_refclk = wrpll.FrequencyMultiplier(platform.request("sma_clkin"))
            self.submodules.wrpll = wrpll.WRPLL(
                platform=self.platform,
                cd_ref=self.wrpll_refclk.cd_ref,
                main_clk_se=clk_synth_se)
            self.csr_devices.append("wrpll_refclk")
            self.csr_devices.append("wrpll")
            self.interrupt_devices.append("wrpll")
            self.config["HAS_SI549"] = None
            self.config["WRPLL_REF_CLK"] = "SMA_CLKIN"
        else:
            if platform.hw_rev == "v2.0":
                self.submodules += SMAClkinForward(self.platform)
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

        self.submodules.gt_drtio = gtp_7series.GTP(
            qpll_channel=self.drtio_qpll_channel,
            data_pads=drtio_data_pads,
            sys_clk_freq=self.clk_freq,
            rtio_clk_freq=rtio_clk_freq)
        self.csr_devices.append("gt_drtio")

        if enable_sata:
            sfp_channels = self.gt_drtio.channels[1:]
        else:
            sfp_channels = self.gt_drtio.channels
        if self.platform.hw_rev in ("v1.0", "v1.1"):
            self.comb += [sfp_ctl.led.eq(channel.rx_ready)
                for sfp_ctl, channel in zip(sfp_ctls, sfp_channels)]
        if self.platform.hw_rev == "v2.0":
            self.comb += [self.virtual_leds.get(i + 1).eq(channel.rx_ready)
                          for i, channel in enumerate(sfp_channels)]

        self.submodules.rtio_tsc = rtio.TSC(glbl_fine_ts_width=3)

        self.drtio_csr_group = []
        self.drtioaux_csr_group = []
        self.drtioaux_memory_group = []
        self.drtio_cri = []
        for i in range(len(self.gt_drtio.channels)):
            core_name = "drtio" + str(i)
            coreaux_name = "drtioaux" + str(i)
            memory_name = "drtioaux" + str(i) + "_mem"
            self.drtio_csr_group.append(core_name)
            self.drtioaux_csr_group.append(coreaux_name)
            self.drtioaux_memory_group.append(memory_name)

            cdr = ClockDomainsRenamer({"rtio_rx": "rtio_rx" + str(i)})

            core = cdr(DRTIOMaster(self.rtio_tsc, self.gt_drtio.channels[i]))
            setattr(self.submodules, core_name, core)
            self.drtio_cri.append(core.cri)
            self.csr_devices.append(core_name)

            coreaux = cdr(DRTIOAuxController(core.link_layer, self.cpu_dw))
            setattr(self.submodules, coreaux_name, coreaux)
            self.csr_devices.append(coreaux_name)

            drtio_aux_mem_size = 1024 * 16 # max_packet * 8 buffers * 2 (tx, rx halves)
            memory_address = self.mem_map["drtioaux"] + drtio_aux_mem_size*i
            self.add_wb_slave(memory_address, drtio_aux_mem_size,
                              coreaux.bus)
            self.add_memory_region(memory_name, memory_address | self.shadow_base, drtio_aux_mem_size)
        self.config["HAS_DRTIO"] = None
        self.config["HAS_DRTIO_ROUTING"] = None
        self.config["DRTIO_ROLE"] = "master"

        rtio_clk_period = 1e9/rtio_clk_freq
        gtp = self.gt_drtio.gtps[0]

        txout_buf = Signal()
        self.specials += Instance("BUFG", i_I=gtp.txoutclk, o_O=txout_buf)
        self.crg.configure(txout_buf, clk_sw=self.gt_drtio.stable_clkin.storage, ext_async_rst=self.crg.clk_sw_fsm.o_clk_sw & ~gtp.tx_init.done)
        self.specials += MultiReg(self.crg.clk_sw_fsm.o_clk_sw & self.crg.mmcm_locked, self.gt_drtio.clk_path_ready, odomain="bootstrap")

        platform.add_period_constraint(gtp.txoutclk, rtio_clk_period)
        platform.add_period_constraint(gtp.rxoutclk, rtio_clk_period)

        platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            gtp.txoutclk, gtp.rxoutclk)
        for gtp in self.gt_drtio.gtps[1:]:
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

    def add_eem_drtio(self, eem_drtio_channels):
        # Must be called before invoking add_rtio() to construct the CRI
        # interconnect properly
        self.submodules.eem_transceiver = eem_serdes.EEMSerdes(self.platform, eem_drtio_channels)
        self.csr_devices.append("eem_transceiver")
        self.config["HAS_DRTIO_EEM"] = None
        self.config["EEM_DRTIO_COUNT"] = len(eem_drtio_channels)

        cdr = ClockDomainsRenamer({"rtio_rx": "sys"})
        for i in range(len(self.eem_transceiver.channels)):
            channel = i + len(self.gt_drtio.channels)
            core_name = "drtio" + str(channel)
            coreaux_name = "drtioaux" + str(channel)
            memory_name = "drtioaux" + str(channel) + "_mem"
            self.drtio_csr_group.append(core_name)
            self.drtioaux_csr_group.append(coreaux_name)
            self.drtioaux_memory_group.append(memory_name)

            core = cdr(DRTIOMaster(self.rtio_tsc, self.eem_transceiver.channels[i]))
            setattr(self.submodules, core_name, core)
            self.drtio_cri.append(core.cri)
            self.csr_devices.append(core_name)

            coreaux = cdr(DRTIOAuxController(core.link_layer, self.cpu_dw))
            setattr(self.submodules, coreaux_name, coreaux)
            self.csr_devices.append(coreaux_name)

            drtio_aux_mem_size = 1024 * 16 # max_packet * 8 buffers * 2 (tx, rx halves)
            memory_address = self.mem_map["drtioaux"] + drtio_aux_mem_size*channel
            self.add_wb_slave(memory_address, drtio_aux_mem_size,
                            coreaux.bus)
            self.add_memory_region(memory_name, memory_address | self.shadow_base, drtio_aux_mem_size)

    def add_drtio_cpuif_groups(self):
        self.add_csr_group("drtio", self.drtio_csr_group)
        self.add_csr_group("drtioaux", self.drtioaux_csr_group)
        self.add_memory_group("drtioaux_mem", self.drtioaux_memory_group)

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


class SatelliteBase(BaseSoC, AMPSoC):
    mem_map = {
        "rtio":          0x20000000,
        "drtioaux":      0x50000000,
        "mailbox":       0x70000000
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, rtio_clk_freq=125e6, enable_sata=False, with_wrpll=False, *, gateware_identifier_str=None, hw_rev="v2.0", **kwargs):
        if hw_rev in ("v1.0", "v1.1"):
            cpu_bus_width = 32
        else:
            cpu_bus_width = 64

        BaseSoC.__init__(self,
                 cpu_type="vexriscv",
                 hw_rev=hw_rev,
                 cpu_bus_width=cpu_bus_width,
                 sdram_controller_type="minicon",
                 l2_size=128*1024,
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
        qpll_drtio_settings = QPLLSettings(
            refclksel=0b001,
            fbdiv=4,
            fbdiv_45=5,
            refclk_div=1)
        qpll = QPLL(cdr_clk, qpll_drtio_settings)
        self.submodules += qpll

        drtio_data_pads = []
        if enable_sata:
            drtio_data_pads.append(platform.request("sata"))
        drtio_data_pads += [platform.request("sfp", i) for i in range(3)]
        if self.platform.hw_rev == "v2.0":
            drtio_data_pads.append(platform.request("sfp", 3))

        if self.platform.hw_rev in ("v1.0", "v1.1"):
            sfp_ctls = [platform.request("sfp_ctl", i) for i in range(3)]
            self.comb += [sc.tx_disable.eq(0) for sc in sfp_ctls]
        self.submodules.gt_drtio = gtp_7series.GTP(
            qpll_channel=qpll.channels[0],
            data_pads=drtio_data_pads,
            sys_clk_freq=self.clk_freq,
            rtio_clk_freq=rtio_clk_freq)
        self.csr_devices.append("gt_drtio")

        if enable_sata:
            sfp_channels = self.gt_drtio.channels[1:]
        else:
            sfp_channels = self.gt_drtio.channels
        if self.platform.hw_rev in ("v1.0", "v1.1"):
            self.comb += [sfp_ctl.led.eq(channel.rx_ready)
                for sfp_ctl, channel in zip(sfp_ctls, sfp_channels)]
        if self.platform.hw_rev == "v2.0":
            self.comb += [self.virtual_leds.get(i).eq(channel.rx_ready)
                          for i, channel in enumerate(sfp_channels)]

        self.submodules.rtio_tsc = rtio.TSC(glbl_fine_ts_width=3)

        self.drtioaux_csr_group = []
        self.drtioaux_memory_group = []
        self.drtiorep_csr_group = []
        self.drtio_cri = []
        for i in range(len(self.gt_drtio.channels)):
            coreaux_name = "drtioaux" + str(i)
            memory_name = "drtioaux" + str(i) + "_mem"
            self.drtioaux_csr_group.append(coreaux_name)
            self.drtioaux_memory_group.append(memory_name)

            cdr = ClockDomainsRenamer({"rtio_rx": "rtio_rx" + str(i)})

            if i == 0:
                self.submodules.rx_synchronizer = cdr(XilinxRXSynchronizer())
                core = cdr(DRTIOSatellite(
                    self.rtio_tsc, self.gt_drtio.channels[i],
                    self.rx_synchronizer))
                self.submodules.drtiosat = core
                self.csr_devices.append("drtiosat")
            else:
                corerep_name = "drtiorep" + str(i-1)
                self.drtiorep_csr_group.append(corerep_name)

                core = cdr(DRTIORepeater(
                    self.rtio_tsc, self.gt_drtio.channels[i]))
                setattr(self.submodules, corerep_name, core)
                self.drtio_cri.append(core.cri)
                self.csr_devices.append(corerep_name)

            coreaux = cdr(DRTIOAuxController(core.link_layer, self.cpu_dw))
            setattr(self.submodules, coreaux_name, coreaux)
            self.csr_devices.append(coreaux_name)

            drtio_aux_mem_size = 1024 * 16 # max_packet * 8 buffers * 2 (tx, rx halves)
            memory_address = self.mem_map["drtioaux"] + drtio_aux_mem_size * i
            self.add_wb_slave(memory_address, drtio_aux_mem_size,
                              coreaux.bus)
            self.add_memory_region(memory_name, memory_address | self.shadow_base, drtio_aux_mem_size)
        self.config["HAS_DRTIO"] = None
        self.config["HAS_DRTIO_ROUTING"] = None
        self.config["DRTIO_ROLE"] = "satellite"

        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1

        rtio_clk_period = 1e9/rtio_clk_freq
        self.config["RTIO_FREQUENCY"] = str(rtio_clk_freq/1e6)

        if with_wrpll:
            clk_synth = platform.request("cdr_clk_clean_fabric")
            clk_synth_se = Signal()
            platform.add_period_constraint(clk_synth.p, 8.0)
            self.specials += Instance("IBUFGDS", p_DIFF_TERM="TRUE", p_IBUF_LOW_PWR="FALSE", i_I=clk_synth.p, i_IB=clk_synth.n, o_O=clk_synth_se)
            self.submodules.wrpll = wrpll.WRPLL(
                platform=self.platform,
                cd_ref=self.gt_drtio.cd_rtio_rx0,
                main_clk_se=clk_synth_se)
            self.submodules.wrpll_skewtester = wrpll.SkewTester(self.rx_synchronizer)
            self.csr_devices.append("wrpll_skewtester")
            self.csr_devices.append("wrpll")
            self.interrupt_devices.append("wrpll")
            self.config["HAS_SI549"] = None
            self.config["WRPLL_REF_CLK"] = "GT_CDR"
        else:
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

        gtp = self.gt_drtio.gtps[0]
        txout_buf = Signal()
        self.specials += Instance("BUFG", i_I=gtp.txoutclk, o_O=txout_buf)
        self.crg.configure(txout_buf, clk_sw=self.gt_drtio.stable_clkin.storage, ext_async_rst=self.crg.clk_sw_fsm.o_clk_sw & ~gtp.tx_init.done)
        self.specials += MultiReg(self.crg.clk_sw_fsm.o_clk_sw & self.crg.mmcm_locked, self.gt_drtio.clk_path_ready, odomain="bootstrap")

        platform.add_period_constraint(gtp.txoutclk, rtio_clk_period)
        platform.add_period_constraint(gtp.rxoutclk, rtio_clk_period)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            gtp.txoutclk, gtp.rxoutclk)
        for gtp in self.gt_drtio.gtps[1:]:
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
            [self.local_io.cri] + self.drtio_cri,
            enable_routing=True)
        self.csr_devices.append("cri_con")
        self.submodules.routing_table = rtio.RoutingTableAccess(self.cri_con)
        self.csr_devices.append("routing_table")
        
        self.submodules.rtio_analyzer = rtio.Analyzer(self.rtio_tsc, self.local_io.cri,
                                                self.get_native_sdram_if(), cpu_dw=self.cpu_dw)
        self.csr_devices.append("rtio_analyzer")

    def add_eem_drtio(self, eem_drtio_channels):
        # Must be called before invoking add_rtio() to construct the CRI
        # interconnect properly
        self.submodules.eem_transceiver = eem_serdes.EEMSerdes(self.platform, eem_drtio_channels)
        self.csr_devices.append("eem_transceiver")
        self.config["HAS_DRTIO_EEM"] = None
        self.config["EEM_DRTIO_COUNT"] = len(eem_drtio_channels)

        cdr = ClockDomainsRenamer({"rtio_rx": "sys"})
        for i in range(len(self.eem_transceiver.channels)):
            channel = i + len(self.gt_drtio.channels)
            corerep_name = "drtiorep" + str(channel-1)
            coreaux_name = "drtioaux" + str(channel)
            memory_name = "drtioaux" + str(channel) + "_mem"
            self.drtiorep_csr_group.append(corerep_name)
            self.drtioaux_csr_group.append(coreaux_name)
            self.drtioaux_memory_group.append(memory_name)

            core = cdr(DRTIORepeater(
                self.rtio_tsc, self.eem_transceiver.channels[i]))
            setattr(self.submodules, corerep_name, core)
            self.drtio_cri.append(core.cri)
            self.csr_devices.append(corerep_name)

            coreaux = cdr(DRTIOAuxController(core.link_layer, self.cpu_dw))
            setattr(self.submodules, coreaux_name, coreaux)
            self.csr_devices.append(coreaux_name)

            drtio_aux_mem_size = 1024 * 16 # max_packet * 8 buffers * 2 (tx, rx halves)
            memory_address = self.mem_map["drtioaux"] + drtio_aux_mem_size*channel
            self.add_wb_slave(memory_address, drtio_aux_mem_size,
                            coreaux.bus)
            self.add_memory_region(memory_name, memory_address | self.shadow_base, drtio_aux_mem_size)

    def add_drtio_cpuif_groups(self):
        self.add_csr_group("drtiorep", self.drtiorep_csr_group)
        self.add_csr_group("drtioaux", self.drtioaux_csr_group)
        self.add_memory_group("drtioaux_mem", self.drtioaux_memory_group)

class GenericStandalone(StandaloneBase):
    def __init__(self, description, hw_rev=None,**kwargs):
        if hw_rev is None:
            hw_rev = description["hw_rev"]
        self.class_name_override = description["variant"]
        StandaloneBase.__init__(self,
            hw_rev=hw_rev,
            with_wrpll=description["enable_wrpll"],
            **kwargs)
        self.config["RTIO_FREQUENCY"] = "{:.1f}".format(description["rtio_frequency"]/1e6)
        if "ext_ref_frequency" in description:
            self.config["SI5324_EXT_REF"] = None
            self.config["EXT_REF_FREQUENCY"] = "{:.1f}".format(
                description["ext_ref_frequency"]/1e6)
        if hw_rev == "v1.0":
            # EEM clock fan-out from Si5324, not MMCX
            self.comb += self.platform.request("clk_sel").eq(1)

        has_grabber = any(peripheral["type"] == "grabber" for peripheral in description["peripherals"])
        if has_grabber:
            self.grabber_csr_group = []

        self.rtio_channels = []
        eem_7series.add_peripherals(self, description["peripherals"])
        if hw_rev in ("v1.0", "v1.1"):
            for i in (1, 2):
                print("SFP LED at RTIO channel 0x{:06x}".format(len(self.rtio_channels)))
                sfp_ctl = self.platform.request("sfp_ctl", i)
                phy = ttl_simple.Output(sfp_ctl.led)
                self.submodules += phy
                self.rtio_channels.append(rtio.Channel.from_phy(phy))
        if hw_rev in ("v1.1", "v2.0"):
            for i in range(3):
                print("USER LED at RTIO channel 0x{:06x}".format(len(self.rtio_channels)))
                phy = ttl_simple.Output(self.platform.request("user_led", i))
                self.submodules += phy
                self.rtio_channels.append(rtio.Channel.from_phy(phy))

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(self.rtio_channels)
        self.rtio_channels.append(rtio.LogChannel())

        self.add_rtio(self.rtio_channels, sed_lanes=description["sed_lanes"])

        if has_grabber:
            self.config["HAS_GRABBER"] = None
            self.add_csr_group("grabber", self.grabber_csr_group)
            for grabber in self.grabber_csr_group:
                self.platform.add_false_path_constraints(
                    self.crg.cd_sys.clk, getattr(self, grabber).deserializer.cd_cl.clk)


class GenericMaster(MasterBase):
    def __init__(self, description, hw_rev=None, **kwargs):
        if hw_rev is None:
            hw_rev = description["hw_rev"]
        self.class_name_override = description["variant"]
        has_drtio_over_eem = any(peripheral["type"] == "shuttler" for peripheral in description["peripherals"])
        MasterBase.__init__(self,
            hw_rev=hw_rev,
            rtio_clk_freq=description["rtio_frequency"],
            enable_sata=description["enable_sata_drtio"],
            enable_sys5x=has_drtio_over_eem,
            with_wrpll=description["enable_wrpll"],
            **kwargs)
        if "ext_ref_frequency" in description:
            self.config["SI5324_EXT_REF"] = None
            self.config["EXT_REF_FREQUENCY"] = "{:.1f}".format(
                description["ext_ref_frequency"]/1e6)
        if hw_rev == "v1.0":
            # EEM clock fan-out from Si5324, not MMCX
            self.comb += self.platform.request("clk_sel").eq(1)

        if has_drtio_over_eem:
            self.eem_drtio_channels = []
        has_grabber = any(peripheral["type"] == "grabber" for peripheral in description["peripherals"])
        if has_grabber:
            self.grabber_csr_group = []

        self.rtio_channels = []
        eem_7series.add_peripherals(self, description["peripherals"])
        if hw_rev in ("v1.1", "v2.0"):
            for i in range(3):
                print("USER LED at RTIO channel 0x{:06x}".format(len(self.rtio_channels)))
                phy = ttl_simple.Output(self.platform.request("user_led", i))
                self.submodules += phy
                self.rtio_channels.append(rtio.Channel.from_phy(phy))

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(self.rtio_channels)
        self.rtio_channels.append(rtio.LogChannel())

        if has_drtio_over_eem:
            self.add_eem_drtio(self.eem_drtio_channels)
        self.add_drtio_cpuif_groups()

        self.add_rtio(self.rtio_channels, sed_lanes=description["sed_lanes"])

        if has_grabber:
            self.config["HAS_GRABBER"] = None
            self.add_csr_group("grabber", self.grabber_csr_group)
            for grabber in self.grabber_csr_group:
                self.platform.add_false_path_constraints(
                    self.gt_drtio.gtps[0].txoutclk, getattr(self, grabber).deserializer.cd_cl.clk)


class GenericSatellite(SatelliteBase):
    def __init__(self, description, hw_rev=None, **kwargs):
        if hw_rev is None:
            hw_rev = description["hw_rev"]
        self.class_name_override = description["variant"]
        has_drtio_over_eem = any(peripheral["type"] == "shuttler" for peripheral in description["peripherals"])
        SatelliteBase.__init__(self,
                               hw_rev=hw_rev,
                               rtio_clk_freq=description["rtio_frequency"],
                               enable_sata=description["enable_sata_drtio"],
                               enable_sys5x=has_drtio_over_eem,
                               with_wrpll=description["enable_wrpll"],
                               **kwargs)
        if hw_rev == "v1.0":
            # EEM clock fan-out from Si5324, not MMCX
            self.comb += self.platform.request("clk_sel").eq(1)
        if has_drtio_over_eem:
            self.eem_drtio_channels = []
        has_grabber = any(peripheral["type"] == "grabber" for peripheral in description["peripherals"])
        if has_grabber:
            self.grabber_csr_group = []

        self.rtio_channels = []
        eem_7series.add_peripherals(self, description["peripherals"])
        if hw_rev in ("v1.1", "v2.0"):
            for i in range(3):
                print("USER LED at RTIO channel 0x{:06x}".format(len(self.rtio_channels)))
                phy = ttl_simple.Output(self.platform.request("user_led", i))
                self.submodules += phy
                self.rtio_channels.append(rtio.Channel.from_phy(phy))

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(self.rtio_channels)
        self.rtio_channels.append(rtio.LogChannel())

        if has_drtio_over_eem:
            self.add_eem_drtio(self.eem_drtio_channels)
        self.add_drtio_cpuif_groups()

        self.add_rtio(self.rtio_channels, sed_lanes=description["sed_lanes"])
        if has_grabber:
            self.config["HAS_GRABBER"] = None
            self.add_csr_group("grabber", self.grabber_csr_group)
            for grabber in self.grabber_csr_group:
                self.platform.add_false_path_constraints(
                    self.gt_drtio.gtps[0].txoutclk, getattr(self, grabber).deserializer.cd_cl.clk)


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder for generic Kasli systems")
    builder_args(parser)
    soc_kasli_args(parser)
    parser.set_defaults(output_dir="artiq_kasli")
    parser.add_argument("description", metavar="DESCRIPTION",
                        help="JSON system description file")
    parser.add_argument("--gateware-identifier-str", default=None,
                        help="Override ROM identifier")
    args = parser.parse_args()
    description = jsondesc.load(args.description)

    min_artiq_version = description["min_artiq_version"]
    if Version(artiq_version) < Version(min_artiq_version):
        logger.warning("ARTIQ version mismatch: current %s < %s minimum",
                       artiq_version, min_artiq_version)

    if description["target"] != "kasli":
        raise ValueError("Description is for a different target")

    if description["drtio_role"] == "standalone":
        cls = GenericStandalone
    elif description["drtio_role"] == "master":
        cls = GenericMaster
    elif description["drtio_role"] == "satellite":
        cls = GenericSatellite
    else:
        raise ValueError("Invalid DRTIO role")

    has_shuttler = any(peripheral["type"] == "shuttler" for peripheral in description["peripherals"])
    if has_shuttler and (description["drtio_role"] == "standalone"):
        raise ValueError("Shuttler requires DRTIO, please switch role to master")
    if description["enable_wrpll"] and description["hw_rev"] in ["v1.0", "v1.1"]:
        raise ValueError("Kasli {} does not support WRPLL".format(description["hw_rev"])) 

    soc = cls(description, gateware_identifier_str=args.gateware_identifier_str, **soc_kasli_argdict(args))
    args.variant = description["variant"]
    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
