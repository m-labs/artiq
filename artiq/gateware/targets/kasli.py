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
from artiq.gateware import eem
from artiq.gateware.drtio.transceiver import gtp_7series
from artiq.gateware.drtio.siphaser import SiPhaser7Series
from artiq.gateware.drtio.rx_synchronizer import XilinxRXSynchronizer
from artiq.gateware.drtio import *
from artiq.build_soc import *


class _RTIOCRG(Module, AutoCSR):
    def __init__(self, platform):
        self.pll_reset = CSRStorage(reset=1)
        self.pll_locked = CSRStatus()
        self.clock_domains.cd_rtio = ClockDomain()
        self.clock_domains.cd_rtiox4 = ClockDomain(reset_less=True)

        clk_synth = platform.request("si5324_clkout_fabric")
        clk_synth_se = Signal()
        platform.add_period_constraint(clk_synth.p, 8.0)
        self.specials += [
            Instance("IBUFGDS",
                p_DIFF_TERM="TRUE", p_IBUF_LOW_PWR="FALSE",
                i_I=clk_synth.p, i_IB=clk_synth.n, o_O=clk_synth_se),
        ]

        pll_locked = Signal()
        rtio_clk = Signal()
        rtiox4_clk = Signal()
        fb_clk = Signal()
        self.specials += [
            Instance("PLLE2_ADV",
                     p_STARTUP_WAIT="FALSE", o_LOCKED=pll_locked,
                     p_BANDWIDTH="HIGH",
                     p_REF_JITTER1=0.001,
                     p_CLKIN1_PERIOD=8.0, p_CLKIN2_PERIOD=8.0,
                     i_CLKIN2=clk_synth_se,
                     # Warning: CLKINSEL=0 means CLKIN2 is selected
                     i_CLKINSEL=0,

                     # VCO @ 1.5GHz when using 125MHz input
                     p_CLKFBOUT_MULT=12, p_DIVCLK_DIVIDE=1,
                     i_CLKFBIN=fb_clk,
                     i_RST=self.pll_reset.storage,

                     o_CLKFBOUT=fb_clk,

                     p_CLKOUT0_DIVIDE=3, p_CLKOUT0_PHASE=0.0,
                     o_CLKOUT0=rtiox4_clk,

                     p_CLKOUT1_DIVIDE=12, p_CLKOUT1_PHASE=0.0,
                     o_CLKOUT1=rtio_clk),
            Instance("BUFG", i_I=rtio_clk, o_O=self.cd_rtio.clk),
            Instance("BUFG", i_I=rtiox4_clk, o_O=self.cd_rtiox4.clk),

            AsyncResetSynchronizer(self.cd_rtio, ~pll_locked),
            MultiReg(pll_locked, self.pll_locked.status)
        ]


def fix_serdes_timing_path(platform):
    # ignore timing of path from OSERDESE2 through the pad to ISERDESE2
    platform.add_platform_command(
        "set_false_path -quiet "
        "-through [get_pins -filter {{REF_PIN_NAME == OQ || REF_PIN_NAME == TQ}} "
            "-of [get_cells -filter {{REF_NAME == OSERDESE2}}]] "
        "-to [get_pins -filter {{REF_PIN_NAME == D}} "
            "-of [get_cells -filter {{REF_NAME == ISERDESE2}}]]"
    )


class StandaloneBase(MiniSoC, AMPSoC):
    mem_map = {
        "cri_con":       0x10000000,
        "rtio":          0x20000000,
        "rtio_dma":      0x30000000,
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

        self.submodules.leds = gpio.GPIOOut(Cat(
            self.platform.request("user_led", 0)))
        self.csr_devices.append("leds")

        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1
        self.config["HAS_SI5324"] = None
        self.config["SI5324_SOFT_RESET"] = None

    def add_rtio(self, rtio_channels):
        self.submodules.rtio_crg = _RTIOCRG(self.platform)
        self.csr_devices.append("rtio_crg")
        fix_serdes_timing_path(self.platform)
        self.submodules.rtio_tsc = rtio.TSC("async", glbl_fine_ts_width=3)
        self.submodules.rtio_core = rtio.Core(self.rtio_tsc, rtio_channels)
        self.csr_devices.append("rtio_core")
        self.submodules.rtio = rtio.KernelInitiator(self.rtio_tsc)
        self.submodules.rtio_dma = ClockDomainsRenamer("sys_kernel")(
            rtio.DMA(self.get_native_sdram_if()))
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

        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.rtio_crg.cd_rtio.clk)

        self.submodules.rtio_analyzer = rtio.Analyzer(self.rtio_tsc, self.rtio_core.cri,
                                                      self.get_native_sdram_if())
        self.csr_devices.append("rtio_analyzer")


class Tester(StandaloneBase):
    """
    Configuration for CI tests. Contains the maximum number of different EEMs.
    """
    def __init__(self, hw_rev=None, **kwargs):
        if hw_rev is None:
            hw_rev = "v1.1"
        StandaloneBase.__init__(self, hw_rev=hw_rev, **kwargs)

        self.config["SI5324_AS_SYNTHESIZER"] = None
        # self.config["SI5324_EXT_REF"] = None
        self.config["RTIO_FREQUENCY"] = "125.0"
        if hw_rev == "v1.0":
            # EEM clock fan-out from Si5324, not MMCX
            self.comb += self.platform.request("clk_sel").eq(1)

        self.rtio_channels = []
        eem.DIO.add_std(self, 5,
            ttl_serdes_7series.InOut_8X, ttl_serdes_7series.Output_8X,
            edge_counter_cls=edge_counter.SimpleEdgeCounter)
        eem.Urukul.add_std(self, 0, 1, ttl_serdes_7series.Output_8X,
                           ttl_simple.ClockGen)
        eem.Sampler.add_std(self, 3, 2, ttl_serdes_7series.Output_8X)
        eem.Zotino.add_std(self, 4, ttl_serdes_7series.Output_8X)

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
            hw_rev = "v1.1"
        StandaloneBase.__init__(self, hw_rev=hw_rev, **kwargs)

        self.config["SI5324_AS_SYNTHESIZER"] = None
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
        eem.SUServo.add_std(
            self, eems_sampler=(3, 2),
            eems_urukul0=(5, 4), eems_urukul1=(7, 6))

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
            pads.clkout, self.rtio_crg.cd_rtio.clk)
        self.platform.add_false_path_constraints(
            pads.clkout, self.crg.cd_sys.clk)


class _RTIOClockMultiplier(Module, AutoCSR):
    def __init__(self, rtio_clk_freq):
        self.pll_reset = CSRStorage(reset=1)
        self.pll_locked = CSRStatus()
        self.clock_domains.cd_rtiox4 = ClockDomain(reset_less=True)

        # See "Global Clock Network Deskew Using Two BUFGs" in ug472.
        clkfbout = Signal()
        clkfbin = Signal()
        rtiox4_clk = Signal()
        pll_locked = Signal()
        self.specials += [
            Instance("MMCME2_BASE",
                p_CLKIN1_PERIOD=1e9/rtio_clk_freq,
                i_CLKIN1=ClockSignal("rtio"),
                i_RST=self.pll_reset.storage,
                o_LOCKED=pll_locked,

                p_CLKFBOUT_MULT_F=8.0, p_DIVCLK_DIVIDE=1,

                o_CLKFBOUT=clkfbout, i_CLKFBIN=clkfbin,

                p_CLKOUT0_DIVIDE_F=2.0, o_CLKOUT0=rtiox4_clk,
            ),
            Instance("BUFG", i_I=clkfbout, o_O=clkfbin),
            Instance("BUFG", i_I=rtiox4_clk, o_O=self.cd_rtiox4.clk),

            MultiReg(pll_locked, self.pll_locked.status)
        ]


class MasterBase(MiniSoC, AMPSoC):
    mem_map = {
        "cri_con":       0x10000000,
        "rtio":          0x20000000,
        "rtio_dma":      0x30000000,
        "drtioaux":      0x50000000,
        "mailbox":       0x70000000
    }
    mem_map.update(MiniSoC.mem_map)

    def __init__(self, rtio_clk_freq=125e6, enable_sata=False, **kwargs):
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

        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1
        self.config["HAS_SI5324"] = None
        self.config["SI5324_SOFT_RESET"] = None
        self.config["SI5324_AS_SYNTHESIZER"] = None
        self.config["RTIO_FREQUENCY"] = str(rtio_clk_freq/1e6)

        drtio_data_pads = []
        if enable_sata:
            drtio_data_pads.append(platform.request("sata"))
        drtio_data_pads += [platform.request("sfp", i) for i in range(1, 3)]

        sfp_ctls = [platform.request("sfp_ctl", i) for i in range(1, 3)]
        self.comb += [sc.tx_disable.eq(0) for sc in sfp_ctls]

        self.submodules.drtio_transceiver = gtp_7series.GTP(
            qpll_channel=self.drtio_qpll_channel,
            data_pads=drtio_data_pads,
            sys_clk_freq=self.clk_freq,
            rtio_clk_freq=rtio_clk_freq)
        self.csr_devices.append("drtio_transceiver")
        self.sync += self.disable_si5324_ibuf.eq(
            ~self.drtio_transceiver.stable_clkin.storage)

        if enable_sata:
            sfp_channels = self.drtio_transceiver.channels[1:]
        else:
            sfp_channels = self.drtio_transceiver.channels
        self.comb += [sfp_ctl.led.eq(channel.rx_ready)
            for sfp_ctl, channel in zip(sfp_ctls, sfp_channels)]

        self.submodules.rtio_tsc = rtio.TSC("async", glbl_fine_ts_width=3)

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
        gtp = self.drtio_transceiver.gtps[0]
        platform.add_period_constraint(gtp.txoutclk, rtio_clk_period)
        platform.add_period_constraint(gtp.rxoutclk, rtio_clk_period)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            gtp.txoutclk, gtp.rxoutclk)
        for gtp in self.drtio_transceiver.gtps[1:]:
            platform.add_period_constraint(gtp.rxoutclk, rtio_clk_period)
            platform.add_false_path_constraints(
                self.crg.cd_sys.clk, gtp.rxoutclk)

        self.submodules.rtio_crg = _RTIOClockMultiplier(rtio_clk_freq)
        self.csr_devices.append("rtio_crg")
        fix_serdes_timing_path(platform)

    def add_rtio(self, rtio_channels):
        # Only add MonInj core if there is anything to monitor
        if any([len(c.probes) for c in rtio_channels]):
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
            [self.rtio_core.cri] + self.drtio_cri,
            enable_routing=True)
        self.register_kernel_cpu_csrdevice("cri_con")
        self.submodules.routing_table = rtio.RoutingTableAccess(self.cri_con)
        self.csr_devices.append("routing_table")

        self.submodules.rtio_analyzer = rtio.Analyzer(self.rtio_tsc, self.cri_con.switch.slave,
                                                      self.get_native_sdram_if())
        self.csr_devices.append("rtio_analyzer")

    # Never running out of stupid features, GTs on A7 make you pack
    # unrelated transceiver PLLs into one GTPE2_COMMON yourself.
    def create_qpll(self):
        # The GTP acts up if you send any glitch to its
        # clock input, even while the PLL is held in reset.
        self.disable_si5324_ibuf = Signal(reset=1)
        self.disable_si5324_ibuf.attr.add("no_retiming")
        si5324_clkout = self.platform.request("si5324_clkout")
        si5324_clkout_buf = Signal()
        self.specials += Instance("IBUFDS_GTE2",
            i_CEB=self.disable_si5324_ibuf,
            i_I=si5324_clkout.p, i_IB=si5324_clkout.n,
            o_O=si5324_clkout_buf)
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
        qpll = QPLL(si5324_clkout_buf, qpll_drtio_settings,
                    self.crg.clk125_buf, qpll_eth_settings)
        self.submodules += qpll
        self.drtio_qpll_channel, self.ethphy_qpll_channel = qpll.channels


class SatelliteBase(BaseSoC):
    mem_map = {
        "drtioaux": 0x50000000,
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, rtio_clk_freq=125e6, enable_sata=False, **kwargs):
        BaseSoC.__init__(self,
                 cpu_type="or1k",
                 sdram_controller_type="minicon",
                 l2_size=128*1024,
                 **kwargs)
        add_identifier(self)

        platform = self.platform

        disable_si5324_ibuf = Signal(reset=1)
        disable_si5324_ibuf.attr.add("no_retiming")
        si5324_clkout = platform.request("si5324_clkout")
        si5324_clkout_buf = Signal()
        self.specials += Instance("IBUFDS_GTE2",
            i_CEB=disable_si5324_ibuf,
            i_I=si5324_clkout.p, i_IB=si5324_clkout.n,
            o_O=si5324_clkout_buf)
        qpll_drtio_settings = QPLLSettings(
            refclksel=0b001,
            fbdiv=4,
            fbdiv_45=5,
            refclk_div=1)
        qpll = QPLL(si5324_clkout_buf, qpll_drtio_settings)
        self.submodules += qpll

        drtio_data_pads = []
        if enable_sata:
            drtio_data_pads.append(platform.request("sata"))
        drtio_data_pads += [platform.request("sfp", i) for i in range(3)]

        sfp_ctls = [platform.request("sfp_ctl", i) for i in range(3)]
        self.comb += [sc.tx_disable.eq(0) for sc in sfp_ctls]
        self.submodules.drtio_transceiver = gtp_7series.GTP(
            qpll_channel=qpll.channels[0],
            data_pads=drtio_data_pads,
            sys_clk_freq=self.clk_freq,
            rtio_clk_freq=rtio_clk_freq)
        self.csr_devices.append("drtio_transceiver")
        self.sync += disable_si5324_ibuf.eq(
            ~self.drtio_transceiver.stable_clkin.storage)

        if enable_sata:
            sfp_channels = self.drtio_transceiver.channels[1:]
        else:
            sfp_channels = self.drtio_transceiver.channels
        self.comb += [sfp_ctl.led.eq(channel.rx_ready)
            for sfp_ctl, channel in zip(sfp_ctls, sfp_channels)]

        self.submodules.rtio_tsc = rtio.TSC("sync", glbl_fine_ts_width=3)

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

            coreaux = cdr(DRTIOAuxController(core.link_layer))
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

        self.config["RTIO_FREQUENCY"] = str(rtio_clk_freq/1e6)
        self.submodules.siphaser = SiPhaser7Series(
            si5324_clkin=platform.request("si5324_clkin"),
            rx_synchronizer=self.rx_synchronizer,
            ref_clk=self.crg.clk125_div2, ref_div2=True,
            rtio_clk_freq=rtio_clk_freq)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk, self.siphaser.mmcm_freerun_output)
        self.csr_devices.append("siphaser")
        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1
        self.config["HAS_SI5324"] = None
        self.config["SI5324_SOFT_RESET"] = None

        rtio_clk_period = 1e9/rtio_clk_freq
        gtp = self.drtio_transceiver.gtps[0]
        platform.add_period_constraint(gtp.txoutclk, rtio_clk_period)
        platform.add_period_constraint(gtp.rxoutclk, rtio_clk_period)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            gtp.txoutclk, gtp.rxoutclk)
        for gtp in self.drtio_transceiver.gtps[1:]:
            platform.add_period_constraint(gtp.rxoutclk, rtio_clk_period)
            platform.add_false_path_constraints(
                self.crg.cd_sys.clk, gtp.rxoutclk)

        self.submodules.rtio_crg = _RTIOClockMultiplier(rtio_clk_freq)
        self.csr_devices.append("rtio_crg")
        fix_serdes_timing_path(platform)

    def add_rtio(self, rtio_channels):
        # Only add MonInj core if there is anything to monitor
        if any([len(c.probes) for c in rtio_channels]):
            self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)
            self.csr_devices.append("rtio_moninj")

        self.submodules.local_io = SyncRTIO(self.rtio_tsc, rtio_channels)
        self.comb += self.drtiosat.async_errors.eq(self.local_io.async_errors)
        self.submodules.cri_con = rtio.CRIInterconnectShared(
            [self.drtiosat.cri],
            [self.local_io.cri] + self.drtio_cri,
            mode="sync", enable_routing=True)
        self.csr_devices.append("cri_con")
        self.submodules.routing_table = rtio.RoutingTableAccess(self.cri_con)
        self.csr_devices.append("routing_table")


class Master(MasterBase):
    def __init__(self, hw_rev=None, **kwargs):
        if hw_rev is None:
            hw_rev = "v1.1"
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
            hw_rev = "v1.1"
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
    args = parser.parse_args()

    variant = args.variant.lower()
    try:
        cls = VARIANTS[variant]
    except KeyError:
        raise SystemExit("Invalid variant (-V/--variant)")

    soc = cls(**soc_kasli_argdict(args))
    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
