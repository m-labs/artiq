#!/usr/bin/env python3

import argparse
import os
import warnings

from migen import *

from misoc.cores import gpio
from misoc.integration.soc_sdram import soc_sdram_args, soc_sdram_argdict
from misoc.integration.builder import builder_args, builder_argdict
from misoc.interconnect.csr import *
from misoc.targets.sayma_amc import BaseSoC, MiniSoC

from artiq.gateware.amp import AMPSoC
from artiq.gateware import serwb
from artiq.gateware import remote_csr
from artiq.gateware import rtio
from artiq.gateware import jesd204_tools
from artiq.gateware.rtio.phy import ttl_simple, sawg
from artiq.gateware.drtio.transceiver import gth_ultrascale
from artiq.gateware.drtio.siphaser import SiPhaser7Series
from artiq.gateware.drtio.rx_synchronizer import XilinxRXSynchronizer
from artiq.gateware.drtio import DRTIOMaster, DRTIOSatellite
from artiq.build_soc import build_artiq_soc
from artiq import __version__ as artiq_version


class AD9154(Module, AutoCSR):
    def __init__(self, platform, sys_crg, jesd_crg, dac):
        self.submodules.jesd = jesd204_tools.UltrascaleTX(
            platform, sys_crg, jesd_crg, dac)

        self.sawgs = [sawg.Channel(width=16, parallelism=4) for i in range(4)]
        self.submodules += self.sawgs

        for conv, ch in zip(self.jesd.core.sink.flatten(), self.sawgs):
            assert len(Cat(ch.o)) == len(conv)
            self.sync.jesd += conv.eq(Cat(ch.o))


class AD9154NoSAWG(Module, AutoCSR):
    def __init__(self, platform, sys_crg, jesd_crg, dac):
        self.submodules.jesd = jesd204_tools.UltrascaleTX(
            platform, sys_crg, jesd_crg, dac)

        self.sawgs = []

        ramp = Signal(4)
        self.sync.rtio += ramp.eq(ramp + 1)

        samples = [[Signal(16) for i in range(4)] for j in range(4)]
        self.comb += [
            a.eq(Cat(b)) for a, b in zip(
                self.jesd.core.sink.flatten(), samples)
        ]
        # ch0: 16-step ramp with big carry toggles
        for i in range(4):
            self.comb += [
                samples[0][i][-4:].eq(ramp),
                samples[0][i][:-4].eq(0x7ff if i % 2 else 0x800)
            ]
        # ch1: 50 MHz
        from math import pi, cos
        data = [int(round(cos(i/12*2*pi)*((1 << 15) - 1)))
                for i in range(12)]
        k = Signal(2)
        self.sync.rtio += If(k == 2, k.eq(0)).Else(k.eq(k + 1))
        self.comb += [
            Case(k, {
                i: [samples[1][j].eq(data[i*4 + j]) for j in range(4)]
                for i in range(3)
            })
        ]
        # ch2: ch0, ch3: ch1
        self.comb += [
            Cat(samples[2]).eq(Cat(samples[0])),
            Cat(samples[3]).eq(Cat(samples[1]))
        ]


class RTMCommon:
    def __init__(self):
        platform = self.platform

        # forward RTM UART to second FTDI UART channel
        serial_1 = platform.request("serial", 1)
        serial_rtm = platform.request("serial_rtm")
        self.comb += [
            serial_1.tx.eq(serial_rtm.rx),
            serial_rtm.tx.eq(serial_1.rx)
        ]

        # RTM bitstream upload
        slave_fpga_cfg = self.platform.request("rtm_fpga_cfg")
        self.submodules.slave_fpga_cfg = gpio.GPIOTristate([
            slave_fpga_cfg.cclk,
            slave_fpga_cfg.din,
            slave_fpga_cfg.done,
            slave_fpga_cfg.init_b,
            slave_fpga_cfg.program_b,
        ])
        self.csr_devices.append("slave_fpga_cfg")
        self.config["SLAVE_FPGA_GATEWARE"] = 0x200000

        # AMC/RTM serwb
        serwb_pads = platform.request("amc_rtm_serwb")
        serwb_phy_amc = serwb.genphy.SERWBPHY(platform.device, serwb_pads, mode="master")
        self.submodules.serwb_phy_amc = serwb_phy_amc
        self.csr_devices.append("serwb_phy_amc")

        serwb_core = serwb.core.SERWBCore(serwb_phy_amc, int(self.clk_freq), mode="slave")
        self.submodules += serwb_core
        self.add_wb_slave(self.mem_map["serwb"], 8192, serwb_core.etherbone.wishbone.bus)


class Standalone(MiniSoC, AMPSoC, RTMCommon):
    """
    Local DAC/SAWG channels only.
    """
    mem_map = {
        "cri_con":       0x10000000,
        "rtio":          0x11000000,
        "rtio_dma":      0x12000000,
        "serwb":         0x13000000,
        "mailbox":       0x70000000
    }
    mem_map.update(MiniSoC.mem_map)

    def __init__(self, with_sawg, **kwargs):
        MiniSoC.__init__(self,
                         cpu_type="or1k",
                         sdram_controller_type="minicon",
                         l2_size=128*1024,
                         ident=artiq_version,
                         ethmac_nrxslots=4,
                         ethmac_ntxslots=4,
                         **kwargs)
        AMPSoC.__init__(self)
        RTMCommon.__init__(self)
        self.config["HMC830_REF"] = "100"

        platform = self.platform

        self.submodules.si5324_rst_n = gpio.GPIOOut(platform.request("si5324").rst_n)
        self.csr_devices.append("si5324_rst_n")
        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1
        self.config["HAS_SI5324"] = None
        self.config["SI5324_AS_SYNTHESIZER"] = None
        self.config["SI5324_SAYMA_REF"] = None

        # RTIO
        rtio_channels = []
        for i in range(4):
            phy = ttl_simple.Output(platform.request("user_led", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))
        sma_io = platform.request("sma_io", 0)
        self.comb += sma_io.direction.eq(1)
        phy = ttl_simple.Output(sma_io.level)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))
        sma_io = platform.request("sma_io", 1)
        self.comb += sma_io.direction.eq(0)
        phy = ttl_simple.InOut(sma_io.level)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))

        self.submodules.ad9154_crg = jesd204_tools.UltrascaleCRG(platform)
        if with_sawg:
            cls = AD9154
        else:
            cls = AD9154NoSAWG
        self.submodules.ad9154_0 = cls(platform, self.crg, self.ad9154_crg, 0)
        self.submodules.ad9154_1 = cls(platform, self.crg, self.ad9154_crg, 1)
        self.csr_devices.append("ad9154_crg")
        self.csr_devices.append("ad9154_0")
        self.csr_devices.append("ad9154_1")
        self.config["HAS_AD9154"] = None
        self.add_csr_group("ad9154", ["ad9154_0", "ad9154_1"])
        self.config["RTIO_FIRST_SAWG_CHANNEL"] = len(rtio_channels)
        rtio_channels.extend(rtio.Channel.from_phy(phy)
                                for sawg in self.ad9154_0.sawgs +
                                            self.ad9154_1.sawgs
                                for phy in sawg.phys)

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.LogChannel())

        self.clock_domains.cd_rtio = ClockDomain()
        self.comb += [
            self.cd_rtio.clk.eq(ClockSignal("jesd")),
            self.cd_rtio.rst.eq(ResetSignal("jesd"))
        ]
        self.submodules.rtio_core = rtio.Core(rtio_channels)
        self.csr_devices.append("rtio_core")
        self.submodules.rtio = rtio.KernelInitiator()
        self.submodules.rtio_dma = ClockDomainsRenamer("sys_kernel")(
            rtio.DMA(self.get_native_sdram_if()))
        self.register_kernel_cpu_csrdevice("rtio")
        self.register_kernel_cpu_csrdevice("rtio_dma")
        self.submodules.cri_con = rtio.CRIInterconnectShared(
            [self.rtio.cri, self.rtio_dma.cri],
            [self.rtio_core.cri])
        self.register_kernel_cpu_csrdevice("cri_con")
        self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)
        self.csr_devices.append("rtio_moninj")

        self.submodules.rtio_analyzer = rtio.Analyzer(self.rtio_core.cri,
                                                      self.get_native_sdram_if())
        self.csr_devices.append("rtio_analyzer")

        self.submodules.sysref_sampler = jesd204_tools.SysrefSampler(
            self.rtio_core.coarse_ts, self.ad9154_crg.jref)
        self.csr_devices.append("sysref_sampler")


class MasterDAC(MiniSoC, AMPSoC, RTMCommon):
    """
    DRTIO master with local DAC/SAWG channels.
    """
    mem_map = {
        "cri_con":       0x10000000,
        "rtio":          0x11000000,
        "rtio_dma":      0x12000000,
        "serwb":         0x13000000,
        "drtio_aux":     0x14000000,
        "mailbox":       0x70000000
    }
    mem_map.update(MiniSoC.mem_map)

    def __init__(self, with_sawg, **kwargs):
        MiniSoC.__init__(self,
                         cpu_type="or1k",
                         sdram_controller_type="minicon",
                         l2_size=128*1024,
                         ident=artiq_version,
                         ethmac_nrxslots=4,
                         ethmac_ntxslots=4,
                         **kwargs)
        AMPSoC.__init__(self)
        RTMCommon.__init__(self)
        self.config["HMC830_REF"] = "100"

        platform = self.platform
        rtio_clk_freq = 150e6

        self.submodules.si5324_rst_n = gpio.GPIOOut(platform.request("si5324").rst_n)
        self.csr_devices.append("si5324_rst_n")
        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1
        self.config["HAS_SI5324"] = None
        self.config["SI5324_AS_SYNTHESIZER"] = None
        self.config["SI5324_SAYMA_REF"] = None

        self.comb += [
            platform.request("sfp_tx_disable", i).eq(0)
            for i in range(2)
        ]
        self.submodules.drtio_transceiver = gth_ultrascale.GTH(
            clock_pads=platform.request("dac_refclk", 0),
            data_pads=[platform.request("sfp", i) for i in range(2)],
            sys_clk_freq=self.clk_freq,
            rtio_clk_freq=rtio_clk_freq)
        self.csr_devices.append("drtio_transceiver")

        drtio_csr_group = []
        drtio_memory_group = []
        drtio_cri = []
        for i in range(2):
            core_name = "drtio" + str(i)
            memory_name = "drtio" + str(i) + "_aux"
            drtio_csr_group.append(core_name)
            drtio_memory_group.append(memory_name)

            core = ClockDomainsRenamer({"rtio_rx": "rtio_rx"+str(i)})(
                DRTIOMaster(self.drtio_transceiver.channels[i]))
            setattr(self.submodules, core_name, core)
            drtio_cri.append(core.cri)
            self.csr_devices.append(core_name)

            memory_address = self.mem_map["drtio_aux"] + 0x800*i
            self.add_wb_slave(memory_address, 0x800,
                              core.aux_controller.bus)
            self.add_memory_region(memory_name, memory_address | self.shadow_base, 0x800)
        self.config["HAS_DRTIO"] = None
        self.add_csr_group("drtio", drtio_csr_group)
        self.add_memory_group("drtio_aux", drtio_memory_group)

        rtio_clk_period = 1e9/rtio_clk_freq
        gth = self.drtio_transceiver.gths[0]
        platform.add_period_constraint(gth.txoutclk, rtio_clk_period)
        platform.add_period_constraint(gth.rxoutclk, rtio_clk_period)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            gth.txoutclk, gth.rxoutclk)
        for gth in self.drtio_transceiver.gths[1:]:
            platform.add_period_constraint(gth.rxoutclk, rtio_clk_period)
            platform.add_false_path_constraints(
                self.crg.cd_sys.clk, gth.rxoutclk)

        rtio_channels = []
        for i in range(4):
            phy = ttl_simple.Output(platform.request("user_led", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))
        sma_io = platform.request("sma_io", 0)
        self.comb += sma_io.direction.eq(1)
        phy = ttl_simple.Output(sma_io.level)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))
        sma_io = platform.request("sma_io", 1)
        self.comb += sma_io.direction.eq(0)
        phy = ttl_simple.InOut(sma_io.level)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))

        self.submodules.ad9154_crg = jesd204_tools.UltrascaleCRG(platform)
        if with_sawg:
            cls = AD9154
        else:
            cls = AD9154NoSAWG
        self.submodules.ad9154_0 = cls(platform, self.crg, self.ad9154_crg, 0)
        self.submodules.ad9154_1 = cls(platform, self.crg, self.ad9154_crg, 1)
        self.csr_devices.append("ad9154_crg")
        self.csr_devices.append("ad9154_0")
        self.csr_devices.append("ad9154_1")
        self.config["HAS_AD9154"] = None
        self.add_csr_group("ad9154", ["ad9154_0", "ad9154_1"])
        self.config["RTIO_FIRST_SAWG_CHANNEL"] = len(rtio_channels)
        rtio_channels.extend(rtio.Channel.from_phy(phy)
                                for sawg in self.ad9154_0.sawgs +
                                            self.ad9154_1.sawgs
                                for phy in sawg.phys)

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.LogChannel())

        self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)
        self.csr_devices.append("rtio_moninj")

        self.submodules.rtio_core = rtio.Core(rtio_channels, glbl_fine_ts_width=3)
        self.csr_devices.append("rtio_core")

        self.submodules.rtio = rtio.KernelInitiator()
        self.submodules.rtio_dma = ClockDomainsRenamer("sys_kernel")(
            rtio.DMA(self.get_native_sdram_if()))
        self.register_kernel_cpu_csrdevice("rtio")
        self.register_kernel_cpu_csrdevice("rtio_dma")
        self.submodules.cri_con = rtio.CRIInterconnectShared(
            [self.rtio.cri, self.rtio_dma.cri],
            [self.rtio_core.cri] + drtio_cri)
        self.register_kernel_cpu_csrdevice("cri_con")

        self.submodules.sysref_sampler = jesd204_tools.SysrefSampler(
            self.rtio_core.coarse_ts, self.ad9154_crg.jref)
        self.csr_devices.append("sysref_sampler")


class Master(MiniSoC, AMPSoC):
    """
    DRTIO master with 2 SFP ports plus 8 lanes on RTM.
    Use passive RTM adapter to connect to satellites.
    Due to GTH clock routing restrictions, it is not possible
    to use more RTM lanes without additional hardware.
    """
    mem_map = {
        "cri_con":       0x10000000,
        "rtio":          0x11000000,
        "rtio_dma":      0x12000000,
        "drtio_aux":     0x14000000,
        "mailbox":       0x70000000
    }
    mem_map.update(MiniSoC.mem_map)

    def __init__(self, with_sawg, **kwargs):
        MiniSoC.__init__(self,
                         cpu_type="or1k",
                         sdram_controller_type="minicon",
                         l2_size=128*1024,
                         ident=artiq_version,
                         ethmac_nrxslots=4,
                         ethmac_ntxslots=4,
                         **kwargs)
        AMPSoC.__init__(self)

        platform = self.platform
        rtio_clk_freq = 150e6

        self.submodules.si5324_rst_n = gpio.GPIOOut(platform.request("si5324").rst_n)
        self.csr_devices.append("si5324_rst_n")
        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1
        self.config["HAS_SI5324"] = None
        self.config["SI5324_AS_SYNTHESIZER"] = None
        self.config["RTIO_FREQUENCY"] = str(rtio_clk_freq/1e6)

        self.comb += [
            platform.request("sfp_tx_disable", i).eq(0)
            for i in range(2)
        ]
        self.submodules.drtio_transceiver = gth_ultrascale.GTH(
            clock_pads=platform.request("si5324_clkout", 0),
            data_pads=[platform.request("sfp", i) for i in range(2)] +
                      [platform.request("rtm_gth", i) for i in range(8)],
            sys_clk_freq=self.clk_freq,
            rtio_clk_freq=rtio_clk_freq)
        self.csr_devices.append("drtio_transceiver")

        drtio_csr_group = []
        drtio_memory_group = []
        drtio_cri = []
        for i in range(10):
            core_name = "drtio" + str(i)
            memory_name = "drtio" + str(i) + "_aux"
            drtio_csr_group.append(core_name)
            drtio_memory_group.append(memory_name)

            core = ClockDomainsRenamer({"rtio_rx": "rtio_rx"+str(i)})(
                DRTIOMaster(self.drtio_transceiver.channels[i]))
            setattr(self.submodules, core_name, core)
            drtio_cri.append(core.cri)
            self.csr_devices.append(core_name)

            memory_address = self.mem_map["drtio_aux"] + 0x800*i
            self.add_wb_slave(memory_address, 0x800,
                              core.aux_controller.bus)
            self.add_memory_region(memory_name, memory_address | self.shadow_base, 0x800)
        self.config["HAS_DRTIO"] = None
        self.add_csr_group("drtio", drtio_csr_group)
        self.add_memory_group("drtio_aux", drtio_memory_group)

        rtio_clk_period = 1e9/rtio_clk_freq
        gth = self.drtio_transceiver.gths[0]
        platform.add_period_constraint(gth.txoutclk, rtio_clk_period)
        platform.add_period_constraint(gth.rxoutclk, rtio_clk_period)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            gth.txoutclk, gth.rxoutclk)
        for gth in self.drtio_transceiver.gths[1:]:
            platform.add_period_constraint(gth.rxoutclk, rtio_clk_period)
            platform.add_false_path_constraints(
                self.crg.cd_sys.clk, gth.rxoutclk)

        rtio_channels = []
        for i in range(4):
            phy = ttl_simple.Output(platform.request("user_led", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))
        sma_io = platform.request("sma_io", 0)
        self.comb += sma_io.direction.eq(1)
        phy = ttl_simple.Output(sma_io.level)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))
        sma_io = platform.request("sma_io", 1)
        self.comb += sma_io.direction.eq(0)
        phy = ttl_simple.InOut(sma_io.level)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.LogChannel())

        self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)
        self.csr_devices.append("rtio_moninj")

        self.submodules.rtio_core = rtio.Core(rtio_channels, glbl_fine_ts_width=3)
        self.csr_devices.append("rtio_core")

        self.submodules.rtio = rtio.KernelInitiator()
        self.submodules.rtio_dma = ClockDomainsRenamer("sys_kernel")(
            rtio.DMA(self.get_native_sdram_if()))
        self.register_kernel_cpu_csrdevice("rtio")
        self.register_kernel_cpu_csrdevice("rtio_dma")
        self.submodules.cri_con = rtio.CRIInterconnectShared(
            [self.rtio.cri, self.rtio_dma.cri],
            [self.rtio_core.cri] + drtio_cri)
        self.register_kernel_cpu_csrdevice("cri_con")


class Satellite(BaseSoC, RTMCommon):
    """
    DRTIO satellite with local DAC/SAWG channels.
    Use SFP0 to connect to master (Kasli/Sayma).
    """
    mem_map = {
        "serwb":         0x13000000,
        "drtio_aux":     0x14000000,
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, with_sawg, **kwargs):
        BaseSoC.__init__(self,
                 cpu_type="or1k",
                 sdram_controller_type="minicon",
                 l2_size=128*1024,
                 ident=artiq_version,
                 **kwargs)
        RTMCommon.__init__(self)
        self.config["HMC830_REF"] = "150"

        platform = self.platform
        rtio_clk_freq = 150e6

        rtio_channels = []
        for i in range(4):
            phy = ttl_simple.Output(platform.request("user_led", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))
        sma_io = platform.request("sma_io", 0)
        self.comb += sma_io.direction.eq(1)
        phy = ttl_simple.Output(sma_io.level)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))
        sma_io = platform.request("sma_io", 1)
        self.comb += sma_io.direction.eq(0)
        phy = ttl_simple.InOut(sma_io.level)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))

        self.submodules.ad9154_crg = jesd204_tools.UltrascaleCRG(
            platform, use_rtio_clock=True)
        if with_sawg:
            cls = AD9154
        else:
            cls = AD9154NoSAWG
        self.submodules.ad9154_0 = cls(platform, self.crg, self.ad9154_crg, 0)
        self.submodules.ad9154_1 = cls(platform, self.crg, self.ad9154_crg, 1)
        self.csr_devices.append("ad9154_crg")
        self.csr_devices.append("ad9154_0")
        self.csr_devices.append("ad9154_1")
        self.config["HAS_AD9154"] = None
        self.add_csr_group("ad9154", ["ad9154_0", "ad9154_1"])
        self.config["RTIO_FIRST_SAWG_CHANNEL"] = len(rtio_channels)
        rtio_channels.extend(rtio.Channel.from_phy(phy)
                                for sawg in self.ad9154_0.sawgs +
                                            self.ad9154_1.sawgs
                                for phy in sawg.phys)

        self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)
        self.csr_devices.append("rtio_moninj")

        self.comb += platform.request("sfp_tx_disable", 0).eq(0)
        self.submodules.drtio_transceiver = gth_ultrascale.GTH(
            clock_pads=platform.request("dac_refclk", 0),
            data_pads=[platform.request("sfp", 0)],
            sys_clk_freq=self.clk_freq,
            rtio_clk_freq=rtio_clk_freq)
        self.csr_devices.append("drtio_transceiver")
        rx0 = ClockDomainsRenamer({"rtio_rx": "rtio_rx0"})
        self.submodules.rx_synchronizer = rx0(XilinxRXSynchronizer())
        self.submodules.drtio0 = rx0(DRTIOSatellite(
            self.drtio_transceiver.channels[0], rtio_channels,
            self.rx_synchronizer))
        self.csr_devices.append("drtio0")
        self.add_wb_slave(self.mem_map["drtio_aux"], 0x800,
                          self.drtio0.aux_controller.bus)
        self.add_memory_region("drtio0_aux", self.mem_map["drtio_aux"] | self.shadow_base, 0x800)
        self.config["HAS_DRTIO"] = None
        self.add_csr_group("drtio", ["drtio0"])
        self.add_memory_group("drtio_aux", ["drtio0_aux"])

        self.config["RTIO_FREQUENCY"] = str(rtio_clk_freq/1e6)
        self.submodules.siphaser = SiPhaser7Series(
            si5324_clkin=platform.request("si5324_clkin"),
            si5324_clkout_fabric=platform.request("adc_sysref"))
        platform.add_platform_command("set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets {mmcm_ps}]",
            mmcm_ps=self.siphaser.mmcm_ps_output)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk, self.siphaser.mmcm_freerun_output)
        self.csr_devices.append("siphaser")
        self.submodules.si5324_rst_n = gpio.GPIOOut(platform.request("si5324").rst_n)
        self.csr_devices.append("si5324_rst_n")
        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1
        self.config["HAS_SI5324"] = None

        self.submodules.sysref_sampler = jesd204_tools.SysrefSampler(
            self.drtio0.coarse_ts, self.ad9154_crg.jref)
        self.csr_devices.append("sysref_sampler")

        rtio_clk_period = 1e9/rtio_clk_freq
        gth = self.drtio_transceiver.gths[0]
        platform.add_period_constraint(gth.txoutclk, rtio_clk_period)
        platform.add_period_constraint(gth.rxoutclk, rtio_clk_period)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            gth.txoutclk, gth.rxoutclk)


def main():
    parser = argparse.ArgumentParser(
        description="Sayma AMC gateware and firmware builder")
    builder_args(parser)
    soc_sdram_args(parser)
    parser.set_defaults(output_dir="artiq_sayma")
    parser.add_argument("-V", "--variant", default="standalone",
        help="variant: "
             "standalone/masterdac/master/satellite "
             "(default: %(default)s)")
    parser.add_argument("--rtm-csr-csv",
        default=os.path.join("artiq_sayma", "rtm_gateware", "rtm_csr.csv"),
        help="CSV file listing remote CSRs on RTM (default: %(default)s)")
    parser.add_argument("--without-sawg",
        default=False, action="store_true",
        help="Remove SAWG RTIO channels feeding the JESD links (speeds up "
        "compilation time). Replaces them with fixed pattern generators.")
    args = parser.parse_args()

    variant = args.variant.lower()
    if variant == "standalone":
        cls = Standalone
    elif variant == "masterdac":
        cls = MasterDAC
    elif variant == "master":
        cls = Master
    elif variant == "satellite":
        cls = Satellite
    else:
        raise SystemExit("Invalid variant (-V/--variant)")
    soc = cls(with_sawg=not args.without_sawg, **soc_sdram_argdict(args))

    if variant != "master":
        remote_csr_regions = remote_csr.get_remote_csr_regions(
            soc.mem_map["serwb"] | soc.shadow_base,
            args.rtm_csr_csv)
        for name, origin, busword, csrs in remote_csr_regions:
            soc.add_csr_region(name, origin, busword, csrs)
        # Configuration for RTM peripherals. Keep in sync with sayma_rtm.py!
        soc.config["HAS_HMC830_7043"] = None
        soc.config["CONVERTER_SPI_HMC830_CS"] = 0
        soc.config["CONVERTER_SPI_HMC7043_CS"] = 1
        soc.config["CONVERTER_SPI_FIRST_AD9154_CS"] = 2

    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
