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
from artiq.gateware.rtio.xilinx_clocking import fix_serdes_timing_path
from artiq.gateware.drtio.transceiver import gtx_7series
from artiq.gateware.drtio.siphaser import SiPhaser7Series
from artiq.gateware.drtio.rx_synchronizer import XilinxRXSynchronizer
from artiq.gateware.drtio import *
from artiq.build_soc import *

class SMAClkinForward(Module):
    def __init__(self, platform):
        sma_clkin = platform.request("user_sma_clock")
        sma_clkin_se = Signal()
        sma_clkin_buffered = Signal()
        cdr_clk_se = Signal()
        cdr_clk = platform.request("si5324_clkin_33")
        self.specials += [
            Instance("IBUFDS", i_I=sma_clkin.p, i_IB=sma_clkin.n, o_O=sma_clkin_se),
            Instance("BUFG", i_I=sma_clkin_se, o_O=sma_clkin_buffered),
            Instance("ODDR", i_C=sma_clkin_buffered, i_CE=1, i_D1=0, i_D2=1, o_Q=cdr_clk_se),
            Instance("OBUFDS", i_I=cdr_clk_se, o_O=cdr_clk.p, o_OB=cdr_clk.n)
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
                         rtio_sys_merge=True,
                         **kwargs)
        AMPSoC.__init__(self)
        add_identifier(self, gateware_identifier_str=gateware_identifier_str)

        self.config["DRTIO_ROLE"] = "standalone"

        if isinstance(self.platform.toolchain, XilinxVivadoToolchain):
            self.platform.toolchain.bitstream_commands.extend([
                "set_property BITSTREAM.GENERAL.COMPRESS True [current_design]",
            ])
        if isinstance(self.platform.toolchain, XilinxISEToolchain):
            self.platform.toolchain.bitgen_opt += " -g compress"

        self.platform.add_extension(_reprogrammed3v3_io)

        cdr_clk_out = self.platform.request("si5324_clkout")
        cdr_clk = Signal()
        cdr_clk_buf = Signal()

        self.config["HAS_SI5324"] = None
        self.submodules.si5324_rst_n = gpio.GPIOOut(self.platform.request("si5324_33").rst_n, reset_out=1)
        self.csr_devices.append("si5324_rst_n")
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

        self.platform.add_period_constraint(cdr_clk_out, 8.)
        self.crg.configure(cdr_clk_buf)

        self.submodules += SMAClkinForward(self.platform)

        self.submodules.timer1 = timer.Timer()
        self.csr_devices.append("timer1")
        self.interrupt_devices.append("timer1")

        self.submodules.leds = gpio.GPIOOut(Cat(
            self.platform.request("user_led", 0),
            self.platform.request("user_led", 1)))
        self.csr_devices.append("leds")

        self.platform.add_extension(_ams101_dac)

        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1

        self.config["HAS_DDS"] = None

    def add_rtio(self, rtio_channels):
        self.submodules.rtio_tsc = rtio.TSC(glbl_fine_ts_width=3)
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
        clk_freq = 100e6 if drtio_100mhz else 125e6
        MiniSoC.__init__(self,
                         cpu_type="vexriscv",
                         cpu_bus_width=64,
                         sdram_controller_type="minicon",
                         l2_size=128*1024,
                         integrated_sram_size=8192,
                         ethmac_nrxslots=4,
                         ethmac_ntxslots=4,
                         clk_freq=clk_freq,
                         rtio_sys_merge=True,
                         **kwargs)
        AMPSoC.__init__(self)
        add_identifier(self, gateware_identifier_str=gateware_identifier_str)

        self.config["DRTIO_ROLE"] = "master"

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

        # 1000BASE_BX10 Ethernet compatible, 100/125MHz RTIO clock
        self.submodules.gt_drtio = gtx_7series.GTX(
            clock_pads=platform.request("si5324_clkout"),
            pads=data_pads,
            clk_freq=self.clk_freq)
        self.csr_devices.append("gt_drtio")

        self.submodules.rtio_tsc = rtio.TSC(glbl_fine_ts_width=3)

        drtio_csr_group = []
        drtioaux_csr_group = []
        drtioaux_memory_group = []
        self.drtio_cri = []
        for i in range(len(self.gt_drtio.channels)):
            core_name = "drtio" + str(i)
            coreaux_name = "drtioaux" + str(i)
            memory_name = "drtioaux" + str(i) + "_mem"
            drtio_csr_group.append(core_name)
            drtioaux_csr_group.append(coreaux_name)
            drtioaux_memory_group.append(memory_name)

            cdr = ClockDomainsRenamer({"rtio_rx": "rtio_rx" + str(i)})

            core = cdr(DRTIOMaster(
                self.rtio_tsc, self.gt_drtio.channels[i]))
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
        self.add_csr_group("drtio", drtio_csr_group)
        self.add_csr_group("drtioaux", drtioaux_csr_group)
        self.add_memory_group("drtioaux_mem", drtioaux_memory_group)

        self.config["RTIO_FREQUENCY"] = str(self.gt_drtio.rtio_clk_freq/1e6)
        self.submodules.si5324_rst_n = gpio.GPIOOut(platform.request("si5324_33").rst_n, reset_out=1)
        self.csr_devices.append("si5324_rst_n")
        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1
        self.config["HAS_SI5324"] = None

        rtio_clk_period = 1e9/self.gt_drtio.rtio_clk_freq
        # Constrain TX & RX timing for the first transceiver channel
        # (First channel acts as master for phase alignment for all channels' TX)
        gtx0 = self.gt_drtio.gtxs[0]

        txout_buf = Signal()
        self.specials += Instance("BUFG", i_I=gtx0.txoutclk, o_O=txout_buf)
        self.crg.configure(txout_buf, clk_sw=self.gt_drtio.stable_clkin.storage, ext_async_rst=self.crg.clk_sw_fsm.o_clk_sw & ~gtx0.tx_init.done)
        self.specials += MultiReg(self.crg.clk_sw_fsm.o_clk_sw & self.crg.mmcm_locked, self.gt_drtio.clk_path_ready, odomain="bootstrap")

        self.comb += [
            platform.request("user_sma_clock_p").eq(ClockSignal("rtio_rx0")),
            platform.request("user_sma_clock_n").eq(gtx0.txoutclk)
        ]

        platform.add_period_constraint(gtx0.txoutclk, rtio_clk_period)
        platform.add_period_constraint(gtx0.rxoutclk, rtio_clk_period)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk, gtx0.rxoutclk)
        # Constrain RX timing for the each transceiver channel
        # (Each channel performs single-lane phase alignment for RX)
        for gtx in self.gt_drtio.gtxs[1:]:
            platform.add_period_constraint(gtx.rxoutclk, rtio_clk_period)
            platform.add_false_path_constraints(
                self.crg.cd_sys.clk, gtx.rxoutclk)

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
        self.submodules.rtio_analyzer = rtio.Analyzer(self.rtio_tsc, self.rtio_core.cri,
                                                self.get_native_sdram_if(), cpu_dw=self.cpu_dw)
        self.csr_devices.append("rtio_analyzer")



class _SatelliteBase(BaseSoC, AMPSoC):
    mem_map = {
        "rtio":         0x20000000,
        "drtioaux":     0x50000000,
        "mailbox":      0x70000000
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, gateware_identifier_str=None, sma_as_sat=False, drtio_100mhz=False, **kwargs):
        clk_freq = 100e6 if drtio_100mhz else 125e6
        BaseSoC.__init__(self,
                 cpu_type="vexriscv",
                 cpu_bus_width=64,
                 sdram_controller_type="minicon",
                 l2_size=128*1024,
                 integrated_sram_size=8192,
                 clk_freq=clk_freq,
                 rtio_sys_merge=True,
                 **kwargs)
        AMPSoC.__init__(self)
        add_identifier(self, gateware_identifier_str=gateware_identifier_str)

        self.config["DRTIO_ROLE"] = "satellite"

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

        rtio_clk_freq = clk_freq

        # 1000BASE_BX10 Ethernet compatible, 100/125MHz RTIO clock
        self.submodules.gt_drtio = gtx_7series.GTX(
            clock_pads=platform.request("si5324_clkout"),
            pads=data_pads,
            clk_freq=self.clk_freq)
        self.csr_devices.append("gt_drtio")

        self.submodules.rtio_tsc = rtio.TSC(glbl_fine_ts_width=3)

        drtioaux_csr_group = []
        drtioaux_memory_group = []
        drtiorep_csr_group = []
        self.drtio_cri = []
        for i in range(len(self.gt_drtio.channels)):
            coreaux_name = "drtioaux" + str(i)
            memory_name = "drtioaux" + str(i) + "_mem"
            drtioaux_csr_group.append(coreaux_name)
            drtioaux_memory_group.append(memory_name)

            cdr = ClockDomainsRenamer({"rtio_rx": "rtio_rx" + str(i)})

            # Satellite
            if i == 0:
                self.submodules.rx_synchronizer = cdr(XilinxRXSynchronizer())
                core = cdr(DRTIOSatellite(
                    self.rtio_tsc, self.gt_drtio.channels[0], self.rx_synchronizer))
                self.submodules.drtiosat = core
                self.csr_devices.append("drtiosat")
            # Repeaters
            else:
                corerep_name = "drtiorep" + str(i-1)
                drtiorep_csr_group.append(corerep_name)
                core = cdr(DRTIORepeater(
                    self.rtio_tsc, self.gt_drtio.channels[i]))
                setattr(self.submodules, corerep_name, core)
                self.drtio_cri.append(core.cri)
                self.csr_devices.append(corerep_name)

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
        self.add_csr_group("drtioaux", drtioaux_csr_group)
        self.add_memory_group("drtioaux_mem", drtioaux_memory_group)
        self.add_csr_group("drtiorep", drtiorep_csr_group)

        self.config["RTIO_FREQUENCY"] = str(self.gt_drtio.rtio_clk_freq/1e6)
        # Si5324 Phaser
        self.submodules.siphaser = SiPhaser7Series(
            si5324_clkin=platform.request("si5324_clkin_33"),
            rx_synchronizer=self.rx_synchronizer,
            ref_clk=ClockSignal("bootstrap"),
            ultrascale=False,
            rtio_clk_freq=self.gt_drtio.rtio_clk_freq)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk, self.siphaser.mmcm_freerun_output)
        self.csr_devices.append("siphaser")
        self.submodules.si5324_rst_n = gpio.GPIOOut(platform.request("si5324_33").rst_n, reset_out=1)
        self.csr_devices.append("si5324_rst_n")
        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1
        self.config["HAS_SI5324"] = None

        rtio_clk_period = 1e9/self.gt_drtio.rtio_clk_freq
        # Constrain TX & RX timing for the first transceiver channel
        # (First channel acts as master for phase alignment for all channels' TX)
        gtx0 = self.gt_drtio.gtxs[0]

        txout_buf = Signal()
        self.specials += Instance("BUFG", i_I=gtx0.txoutclk, o_O=txout_buf)
        self.crg.configure(txout_buf, clk_sw=self.gt_drtio.stable_clkin.storage, ext_async_rst=self.crg.clk_sw_fsm.o_clk_sw & ~gtx0.tx_init.done)
        self.specials += MultiReg(self.crg.clk_sw_fsm.o_clk_sw & self.crg.mmcm_locked, self.gt_drtio.clk_path_ready, odomain="bootstrap")

        self.comb += [
            platform.request("user_sma_clock_p").eq(ClockSignal("rtio_rx0")),
            platform.request("user_sma_clock_n").eq(gtx0.txoutclk)
        ]

        platform.add_period_constraint(gtx0.txoutclk, rtio_clk_period)
        platform.add_period_constraint(gtx0.rxoutclk, rtio_clk_period)
        # Constrain RX timing for the each transceiver channel
        # (Each channel performs single-lane phase alignment for RX)
        for gtx in self.gt_drtio.gtxs[1:]:
            platform.add_period_constraint(gtx.rxoutclk, rtio_clk_period)
            platform.add_false_path_constraints(
                self.crg.cd_sys.clk, gtx.rxoutclk)

        fix_serdes_timing_path(platform)

    def add_rtio(self, rtio_channels):
        self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)
        self.csr_devices.append("rtio_moninj")

        # DRTIO
        self.submodules.local_io = SyncRTIO(self.rtio_tsc, rtio_channels)
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
