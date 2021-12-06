#!/usr/bin/env python3

import argparse

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.cdc import MultiReg
from migen.build.generic_platform import *
from migen.build.xilinx.vivado import XilinxVivadoToolchain
from migen.build.xilinx.ise import XilinxISEToolchain

from misoc.interconnect.csr import *
from misoc.cores import gpio, timer
from misoc.targets.kc705 import BaseSoC, MiniSoC, soc_kc705_args, soc_kc705_argdict
from misoc.integration.builder import builder_args, builder_argdict

from artiq.gateware.amp import AMPSoC
from artiq.gateware import rtio, nist_clock, nist_qc2
from artiq.gateware.rtio.phy import ttl_simple, ttl_serdes_7series, dds, spi2
from artiq.gateware.rtio.xilinx_clocking import RTIOClockMultiplier, fix_serdes_timing_path
from artiq.gateware.drtio.transceiver import gtx_7series
from artiq.gateware.drtio.siphaser import SiPhaser7Series
from artiq.gateware.drtio.rx_synchronizer import XilinxRXSynchronizer
from artiq.gateware.drtio import *
from artiq.build_soc import *


class _RTIOCRG(Module, AutoCSR):
    def __init__(self, platform, rtio_internal_clk, use_sma=True):
        self._clock_sel = CSRStorage()
        self._pll_reset = CSRStorage(reset=1)
        self._pll_locked = CSRStatus()
        self.clock_domains.cd_rtio = ClockDomain()
        self.clock_domains.cd_rtiox4 = ClockDomain(reset_less=True)

        # 100 MHz when using 125MHz input
        self.clock_domains.cd_ext_clkout = ClockDomain(reset_less=True)
        platform.add_period_constraint(self.cd_ext_clkout.clk, 5.0)
        if use_sma:
            ext_clkout = platform.request("user_sma_gpio_p_33")
            self.sync.ext_clkout += ext_clkout.eq(~ext_clkout)

        rtio_external_clk = Signal()
        if use_sma:
            user_sma_clock = platform.request("user_sma_clock")
            platform.add_period_constraint(user_sma_clock.p, 8.0)
            self.specials += Instance("IBUFDS",
                                      i_I=user_sma_clock.p, i_IB=user_sma_clock.n,
                                      o_O=rtio_external_clk)

        pll_locked = Signal()
        rtio_clk = Signal()
        rtiox4_clk = Signal()
        ext_clkout_clk = Signal()
        self.specials += [
            Instance("PLLE2_ADV",
                     p_STARTUP_WAIT="FALSE", o_LOCKED=pll_locked,

                     p_REF_JITTER1=0.01,
                     p_CLKIN1_PERIOD=8.0, p_CLKIN2_PERIOD=8.0,
                     i_CLKIN1=rtio_internal_clk, i_CLKIN2=rtio_external_clk,
                     # Warning: CLKINSEL=0 means CLKIN2 is selected
                     i_CLKINSEL=~self._clock_sel.storage,

                     # VCO @ 1GHz when using 125MHz input
                     p_CLKFBOUT_MULT=8, p_DIVCLK_DIVIDE=1,
                     i_CLKFBIN=self.cd_rtio.clk,
                     i_RST=self._pll_reset.storage,

                     o_CLKFBOUT=rtio_clk,

                     p_CLKOUT0_DIVIDE=2, p_CLKOUT0_PHASE=0.0,
                     o_CLKOUT0=rtiox4_clk,

                     p_CLKOUT1_DIVIDE=5, p_CLKOUT1_PHASE=0.0,
                     o_CLKOUT1=ext_clkout_clk),
            Instance("BUFG", i_I=rtio_clk, o_O=self.cd_rtio.clk),
            Instance("BUFG", i_I=rtiox4_clk, o_O=self.cd_rtiox4.clk),
            Instance("BUFG", i_I=ext_clkout_clk, o_O=self.cd_ext_clkout.clk),

            AsyncResetSynchronizer(self.cd_rtio, ~pll_locked),
            MultiReg(pll_locked, self._pll_locked.status)
        ]


# The default voltage for these signals on KC705 is 2.5V, and the Migen platform
# follows this default. But since the SMAs are on the same bank as the DDS,
# which is set to 3.3V by reprogramming the KC705 power ICs, we need to
# redefine them here.
_reprogrammed3v3_io = [
    ("user_sma_gpio_p_33", 0, Pins("Y23"), IOStandard("LVCMOS33")),
    ("user_sma_gpio_n_33", 0, Pins("Y24"), IOStandard("LVCMOS33")),
    ("si5324_33", 0,
        Subsignal("rst_n", Pins("AE20"), IOStandard("LVCMOS33")),
        Subsignal("int", Pins("AG24"), IOStandard("LVCMOS33"))
    ),
    ("sfp_tx_disable_n_33", 0, Pins("Y20"), IOStandard("LVCMOS33")),
    # HACK: this should be LVDS, but TMDS is the only supported differential
    # output standard at 3.3V. KC705 hardware design issue?
    ("si5324_clkin_33", 0,
        Subsignal("p", Pins("W27"), IOStandard("TMDS_33")),
        Subsignal("n", Pins("W28"), IOStandard("TMDS_33"))
    ),
    ("sdcard_spi_33", 0,
        Subsignal("miso", Pins("AC20"), Misc("PULLUP=TRUE")),
        Subsignal("clk", Pins("AB23")),
        Subsignal("mosi", Pins("AB22")),
        Subsignal("cs_n", Pins("AC21")),
        IOStandard("LVCMOS33")
    )
]

_ams101_dac = [
    ("ams101_dac", 0,
        Subsignal("ldac", Pins("XADC:GPIO0")),
        Subsignal("clk", Pins("XADC:GPIO1")),
        Subsignal("mosi", Pins("XADC:GPIO2")),
        Subsignal("cs_n", Pins("XADC:GPIO3")),
        IOStandard("LVTTL")
     )
]

class _StandaloneBase(MiniSoC, AMPSoC):
    mem_map = {
        "cri_con":       0x10000000,
        "rtio":          0x20000000,
        "rtio_dma":      0x30000000,
        "mailbox":       0x70000000
    }
    mem_map.update(MiniSoC.mem_map)

    def __init__(self, gateware_identifier_str=None, drtio_100mhz=False, **kwargs):
        MiniSoC.__init__(self,
                         cpu_type="vexriscv",
                         cpu_bus_width=64,
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

        self.submodules.timer1 = timer.Timer()
        self.csr_devices.append("timer1")
        self.interrupt_devices.append("timer1")

        self.submodules.leds = gpio.GPIOOut(Cat(
            self.platform.request("user_led", 0),
            self.platform.request("user_led", 1)))
        self.csr_devices.append("leds")

        self.platform.add_extension(_reprogrammed3v3_io)
        self.platform.add_extension(_ams101_dac)

        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1

        self.config["HAS_DDS"] = None

    def add_rtio(self, rtio_channels):
        self.submodules.rtio_crg = _RTIOCRG(self.platform, self.crg.cd_sys.clk)
        self.csr_devices.append("rtio_crg")
        self.config["HAS_RTIO_CLOCK_SWITCH"] = None
        self.submodules.rtio_tsc = rtio.TSC("async", glbl_fine_ts_width=3)
        self.submodules.rtio_core = rtio.Core(self.rtio_tsc, rtio_channels)
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
        self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)
        self.csr_devices.append("rtio_moninj")

        self.platform.add_period_constraint(self.rtio_crg.cd_rtio.clk, 8.)
        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.rtio_crg.cd_rtio.clk)

        self.submodules.rtio_analyzer = rtio.Analyzer(self.rtio_tsc, self.rtio_core.cri,
                                                      self.get_native_sdram_if(), cpu_dw=self.cpu_dw)
        self.csr_devices.append("rtio_analyzer")


class _MasterBase(MiniSoC, AMPSoC):
    mem_map = {
        "cri_con":      0x10000000,
        "rtio":         0x20000000,
        "rtio_dma":     0x30000000,
        "drtioaux":     0x50000000,
        "mailbox":      0x70000000
    }
    mem_map.update(MiniSoC.mem_map)

    def __init__(self, gateware_identifier_str=None, drtio_100mhz=False, **kwargs):
        MiniSoC.__init__(self,
                         cpu_type="vexriscv",
                         cpu_bus_width=64,
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
        platform.add_extension(_reprogrammed3v3_io)
        platform.add_extension(_ams101_dac)

        self.comb += platform.request("sfp_tx_disable_n_33").eq(1)
        data_pads = [
            platform.request("sfp"), platform.request("user_sma_mgt")
        ]

        rtio_clk_freq = 100e6 if drtio_100mhz else 125e6

        # 1000BASE_BX10 Ethernet compatible, 100/125MHz RTIO clock
        self.submodules.drtio_transceiver = gtx_7series.GTX(
            clock_pads=platform.request("si5324_clkout"),
            pads=data_pads,
            sys_clk_freq=self.clk_freq,
            rtio_clk_freq=rtio_clk_freq)
        self.csr_devices.append("drtio_transceiver")

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

            core = cdr(DRTIOMaster(
                self.rtio_tsc, self.drtio_transceiver.channels[i]))
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

        self.config["RTIO_FREQUENCY"] = str(self.drtio_transceiver.rtio_clk_freq/1e6)
        self.submodules.si5324_rst_n = gpio.GPIOOut(platform.request("si5324_33").rst_n)
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

        self.submodules.rtio_crg = RTIOClockMultiplier(self.drtio_transceiver.rtio_clk_freq)
        self.csr_devices.append("rtio_crg")
        fix_serdes_timing_path(platform)

    def add_rtio(self, rtio_channels):
        self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)
        self.csr_devices.append("rtio_moninj")

        self.submodules.rtio_core = rtio.Core(self.rtio_tsc, rtio_channels)
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


class _SatelliteBase(BaseSoC):
    mem_map = {
        "drtioaux":     0x50000000,
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, gateware_identifier_str=None, sma_as_sat=False, drtio_100mhz=False, **kwargs):
        BaseSoC.__init__(self,
                 cpu_type="vexriscv",
                 cpu_bus_width=64,
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
        platform.add_extension(_reprogrammed3v3_io)
        platform.add_extension(_ams101_dac)

        self.comb += platform.request("sfp_tx_disable_n_33").eq(1)
        data_pads = [
            platform.request("sfp"), platform.request("user_sma_mgt")
        ]
        if sma_as_sat:
            data_pads = data_pads[::-1]

        rtio_clk_freq = 100e6 if drtio_100mhz else 125e6

        # 1000BASE_BX10 Ethernet compatible, 100/125MHz RTIO clock
        self.submodules.drtio_transceiver = gtx_7series.GTX(
            clock_pads=platform.request("si5324_clkout"),
            pads=data_pads,
            sys_clk_freq=self.clk_freq,
            rtio_clk_freq=rtio_clk_freq)
        self.csr_devices.append("drtio_transceiver")

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

            # Satellite
            if i == 0:
                self.submodules.rx_synchronizer = cdr(XilinxRXSynchronizer())
                core = cdr(DRTIOSatellite(
                    self.rtio_tsc, self.drtio_transceiver.channels[0], self.rx_synchronizer))
                self.submodules.drtiosat = core
                self.csr_devices.append("drtiosat")
            # Repeaters
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

        self.config["RTIO_FREQUENCY"] = str(self.drtio_transceiver.rtio_clk_freq/1e6)
        # Si5324 Phaser
        self.submodules.siphaser = SiPhaser7Series(
            si5324_clkin=platform.request("si5324_clkin_33"),
            rx_synchronizer=self.rx_synchronizer,
            ultrascale=False,
            rtio_clk_freq=self.drtio_transceiver.rtio_clk_freq)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk, self.siphaser.mmcm_freerun_output)
        self.csr_devices.append("siphaser")
        self.submodules.si5324_rst_n = gpio.GPIOOut(platform.request("si5324_33").rst_n)
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

        self.submodules.rtio_crg = RTIOClockMultiplier(self.drtio_transceiver.rtio_clk_freq)
        self.csr_devices.append("rtio_crg")
        fix_serdes_timing_path(platform)

    def add_rtio(self, rtio_channels):
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


class _NIST_CLOCK_RTIO:
    """
    NIST clock hardware, with old backplane and 11 DDS channels
    """
    def __init__(self):
        platform = self.platform
        platform.add_extension(nist_clock.fmc_adapter_io)

        rtio_channels = []
        for i in range(16):
            if i % 4 == 3:
                phy = ttl_serdes_7series.InOut_8X(platform.request("ttl", i))
                self.submodules += phy
                rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=512))
            else:
                phy = ttl_serdes_7series.Output_8X(platform.request("ttl", i))
                self.submodules += phy
                rtio_channels.append(rtio.Channel.from_phy(phy))

        for i in range(2):
            phy = ttl_serdes_7series.InOut_8X(platform.request("pmt", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=512))

        phy = ttl_serdes_7series.InOut_8X(platform.request("user_sma_gpio_n_33"))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=512))

        phy = ttl_simple.Output(platform.request("user_led", 2))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))

        ams101_dac = self.platform.request("ams101_dac", 0)
        phy = ttl_simple.Output(ams101_dac.ldac)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))

        phy = ttl_simple.ClockGen(platform.request("la32_p"))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))

        phy = spi2.SPIMaster(ams101_dac)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(
            phy, ififo_depth=4))

        for i in range(3):
            phy = spi2.SPIMaster(self.platform.request("spi", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(
                phy, ififo_depth=128))

        phy = spi2.SPIMaster(platform.request("sdcard_spi_33"))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(
            phy, ififo_depth=4))

        phy = dds.AD9914(platform.request("dds"), 11, onehot=True)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.LogChannel())

        self.add_rtio(rtio_channels)


class _NIST_QC2_RTIO:
    """
    NIST QC2 hardware, as used in Quantum I and Quantum II, with new backplane
    and 24 DDS channels.  Two backplanes are used.
    """
    def __init__(self):
        platform = self.platform
        platform.add_extension(nist_qc2.fmc_adapter_io)

        rtio_channels = []
        clock_generators = []

        # All TTL channels are In+Out capable
        for i in range(40):
            phy = ttl_serdes_7series.InOut_8X(
                platform.request("ttl", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=512))

        # CLK0, CLK1 are for clock generators, on backplane SMP connectors
        for i in range(2):
            phy = ttl_simple.ClockGen(
                platform.request("clkout", i))
            self.submodules += phy
            clock_generators.append(rtio.Channel.from_phy(phy))

        # user SMA on KC705 board
        phy = ttl_serdes_7series.InOut_8X(platform.request("user_sma_gpio_n_33"))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=512))

        phy = ttl_simple.Output(platform.request("user_led", 2))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))

        # AMS101 DAC on KC705 XADC header - optional
        ams101_dac = self.platform.request("ams101_dac", 0)
        phy = ttl_simple.Output(ams101_dac.ldac)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))

        # add clock generators after TTLs
        rtio_channels += clock_generators

        phy = spi2.SPIMaster(ams101_dac)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(
            phy, ififo_depth=4))

        for i in range(4):
            phy = spi2.SPIMaster(self.platform.request("spi", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(
                phy, ififo_depth=128))

        for backplane_offset in range(2):
            phy = dds.AD9914(
                platform.request("dds", backplane_offset), 12, onehot=True)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.LogChannel())

        self.add_rtio(rtio_channels)


class NIST_CLOCK(_StandaloneBase, _NIST_CLOCK_RTIO):
    def __init__(self, **kwargs):
        _StandaloneBase.__init__(self, **kwargs)
        _NIST_CLOCK_RTIO.__init__(self)


class NIST_QC2(_StandaloneBase, _NIST_QC2_RTIO):
    def __init__(self, **kwargs):
        _StandaloneBase.__init__(self, **kwargs)
        _NIST_QC2_RTIO.__init__(self)


class NIST_CLOCK_Master(_MasterBase, _NIST_CLOCK_RTIO):
    def __init__(self, **kwargs):
        _MasterBase.__init__(self, **kwargs)
        _NIST_CLOCK_RTIO.__init__(self)


class NIST_QC2_Master(_MasterBase, _NIST_QC2_RTIO):
    def __init__(self, **kwargs):
        _MasterBase.__init__(self, **kwargs)
        _NIST_QC2_RTIO.__init__(self)


class NIST_CLOCK_Satellite(_SatelliteBase, _NIST_CLOCK_RTIO):
    def __init__(self, **kwargs):
        _SatelliteBase.__init__(self, **kwargs)
        _NIST_CLOCK_RTIO.__init__(self)


class NIST_QC2_Satellite(_SatelliteBase, _NIST_QC2_RTIO):
    def __init__(self, **kwargs):
        _SatelliteBase.__init__(self, **kwargs)
        _NIST_QC2_RTIO.__init__(self)


VARIANT_CLS = [
    NIST_CLOCK, NIST_QC2,
    NIST_CLOCK_Master, NIST_QC2_Master,
    NIST_CLOCK_Satellite, NIST_QC2_Satellite,
]
VARIANTS = {cls.__name__.lower(): cls for cls in VARIANT_CLS}


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder for KC705 systems")
    builder_args(parser)
    soc_kc705_args(parser)
    parser.set_defaults(output_dir="artiq_kc705")
    parser.add_argument("-V", "--variant", default="nist_clock",
                        help="variant: "
                             "[standalone: nist_clock/nist_qc2] "
                             "[DRTIO master: nist_clock_master/nist_qc2_master] "
                             "[DRTIO satellite: nist_clock_satellite/nist_qc2_satellite]  "
                             "(default: %(default)s)")
    parser.add_argument("--gateware-identifier-str", default=None,
                        help="Override ROM identifier")
    parser.add_argument("--drtio100mhz", action="store_true", default=False,
                        help="DRTIO systems only - use 100MHz RTIO clock")
    args = parser.parse_args()

    variant = args.variant.lower()
    try:
        cls = VARIANTS[variant]
    except KeyError:
        raise SystemExit("Invalid variant (-V/--variant)")

    soc = cls(gateware_identifier_str=args.gateware_identifier_str, drtio_100mhz=args.drtio100mhz, **soc_kc705_argdict(args))
    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
