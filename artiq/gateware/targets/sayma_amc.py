#!/usr/bin/env python3

import argparse
import os
import warnings
from functools import partial

from migen import *
from migen.build.generic_platform import IOStandard

from misoc.cores import gpio
from misoc.integration.builder import builder_args, builder_argdict
from misoc.interconnect.csr import *
from misoc.targets.sayma_amc import *

from artiq.gateware.amp import AMPSoC
from artiq.gateware import eem
from artiq.gateware import rtio
from artiq.gateware import jesd204_tools
from artiq.gateware import fmcdio_vhdci_eem
from artiq.gateware.rtio.phy import ttl_simple, ttl_serdes_ultrascale, sawg
from artiq.gateware.drtio.transceiver import gth_ultrascale
from artiq.gateware.drtio.siphaser import SiPhaser7Series
from artiq.gateware.drtio.rx_synchronizer import XilinxRXSynchronizer
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


class RTMUARTForward(Module):
    def __init__(self, platform):
        # forward RTM UART to second FTDI UART channel
        serial_1 = platform.request("serial", 1)
        serial_rtm = platform.request("serial_rtm")
        self.comb += [
            serial_1.tx.eq(serial_rtm.rx),
            serial_rtm.tx.eq(serial_1.rx)
        ]


class SatelliteBase(MiniSoC):
    mem_map = {
        "drtioaux":      0x14000000,
    }
    mem_map.update(MiniSoC.mem_map)

    def __init__(self, rtio_clk_freq=125e6, identifier_suffix="", gateware_identifier_str=None, with_sfp=False, **kwargs):
        MiniSoC.__init__(self,
                 cpu_type="or1k",
                 sdram_controller_type="minicon",
                 l2_size=128*1024,
                 integrated_sram_size=8192,
                 ethmac_nrxslots=4,
                 ethmac_ntxslots=4,
                 **kwargs)
        add_identifier(self, suffix=identifier_suffix, gateware_identifier_str=gateware_identifier_str)
        self.rtio_clk_freq = rtio_clk_freq

        platform = self.platform

        if with_sfp:
            # Use SFP0 to connect to master (Kasli)
            self.comb += platform.request("sfp_tx_disable", 0).eq(0)
            drtio_uplink = platform.request("sfp", 0)
        else:
            drtio_uplink = platform.request("fat_pipe", 0)
        self.submodules.drtio_transceiver = gth_ultrascale.GTH(
            clock_pads=platform.request("cdr_clk_clean"),
            data_pads=[drtio_uplink, platform.request("rtm_amc_link")],
            sys_clk_freq=self.clk_freq,
            rtio_clk_freq=rtio_clk_freq,
            clock_recout_pads=None)
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

        rtio_clk_period = 1e9/rtio_clk_freq
        self.config["RTIO_FREQUENCY"] = str(rtio_clk_freq/1e6)
        self.comb += platform.request("filtered_clk_sel").eq(1)
        self.submodules.siphaser = SiPhaser7Series(
            si5324_clkin=platform.request("si5324_clkin"),
            rx_synchronizer=self.rx_synchronizer,
            ultrascale=True,
            rtio_clk_freq=rtio_clk_freq)
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

        gth = self.drtio_transceiver.gths[0]
        platform.add_period_constraint(gth.txoutclk, rtio_clk_period/2)
        platform.add_period_constraint(gth.rxoutclk, rtio_clk_period)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            gth.txoutclk, gth.rxoutclk)

        # SSP1
        # (Note: append() to csr_devices automatically adds "HAS_DEVICE_NAME_UPPERCASE"
        #  to Rust cfg, by misoc.integration.cpu_interface.get_rust_cfg().)

        # MMC SPI GPIO input submodule
        class Mmcspi(Module, AutoCSR):
            def __init__(self, ssp):
                self.submodules.cs_n = gpio.GPIOIn(ssp.cs_n)
                self.submodules.clk = gpio.GPIOIn(ssp.clk)
                self.submodules.mosi = gpio.GPIOIn(ssp.mosi)

        # SPI GPIO core for bitbanging
        ssp1 = self.platform.request("ssp1")
        self.submodules.mmcspi = Mmcspi(ssp1)
        self.csr_devices.append("mmcspi")

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


# JESD204 DAC Channel Group
class JDCGSAWG(Module, AutoCSR):
    def __init__(self, platform, sys_crg, jesd_crg, dac):
        # Kintex Ultrascale GTH, speed grade -1C:
        # QPLL0 linerate (D=1): 9.8 - 12.5 Gb/s
        self.submodules.jesd = jesd204_tools.UltrascaleTX(
            platform, sys_crg, jesd_crg, dac, pll_type="qpll", tx_half=True)

        self.submodules.sawgs = [sawg.Channel(width=16, parallelism=8) for i in range(4)]

        for conv, ch in zip(self.jesd.core.sink.flatten(), self.sawgs):
            assert len(Cat(ch.o)) == len(conv)
            self.sync.jesd += conv.eq(Cat(ch.o))


class JDCGPattern(Module, AutoCSR):
    def __init__(self, platform, sys_crg, jesd_crg, dac):
        self.submodules.jesd = jesd204_tools.UltrascaleTX(
            platform, sys_crg, jesd_crg, dac, pll_type="qpll", tx_half=True)

        self.sawgs = []

        ramp = Signal(4)
        self.sync.rtio += ramp.eq(ramp + 1)

        samples = [[Signal(16) for i in range(8)] for j in range(4)]
        self.comb += [
            a.eq(Cat(b)) for a, b in zip(
                self.jesd.core.sink.flatten(), samples)
        ]
        # ch0: 16-step ramp with big carry toggles
        for i in range(8):
            self.comb += [
                samples[0][i][-4:].eq(ramp),
                samples[0][i][:-4].eq(0x7ff if i % 2 else 0x800)
            ]
        # ch1: 50 MHz
        # - Formulae:
        #                   target cosine wave frequency:    f = 50e6
        #                         DAC sampling frequency:   fs = 1000e6
        #       number of samples per coarse RTIO period:    P = 8
        #       number of samples needed per wave period:    M = (1/f) / (1/fs)) = 20
        #             number of repeating samples needed:    N = LCM(P, M) = 40
        #    number of RTIO periods needed for repeating:    k = N/P = 5
        #                  discretized value of the wave: y[i] = cos(i/M * 2pi)
        from math import pi, cos
        data = [int(round(cos(i/20*2*pi)*((1 << 15) - 1)))
                for i in range(40)]
        k = Signal(max=5)
        self.sync.rtio += If(k == 4, k.eq(0)).Else(k.eq(k + 1))
        self.comb += [
            Case(k, {
                i: [samples[1][j].eq(data[i*8 + j]) for j in range(8)]
                for i in range(5)
            })
        ]
        # ch2: ch0, ch3: ch1
        self.comb += [
            Cat(samples[2]).eq(Cat(samples[0])),
            Cat(samples[3]).eq(Cat(samples[1]))
        ]


class JDCGSyncDDS(Module, AutoCSR):
    def __init__(self, platform, sys_crg, jesd_crg, dac):
        self.submodules.jesd = jesd204_tools.UltrascaleTX(
            platform, sys_crg, jesd_crg, dac, pll_type="qpll", tx_half=True)
        self.coarse_ts = Signal(32)

        self.sawgs = []

        ftw = round(2**len(self.coarse_ts)*9e6/1000e6)
        parallelism = 8

        mul_1 = Signal.like(self.coarse_ts)
        mul_2 = Signal.like(self.coarse_ts)
        mul_3 = Signal.like(self.coarse_ts)
        self.sync.rtio += [
            mul_1.eq(self.coarse_ts*ftw*parallelism),
            mul_2.eq(mul_1),
            mul_3.eq(mul_2)
        ]

        phases = [Signal.like(self.coarse_ts) for i in range(parallelism)]
        self.sync.rtio += [phases[i].eq(mul_3 + i*ftw) for i in range(parallelism)]

        resolution = 10
        steps = 2**resolution
        from math import pi, cos
        data = [(2**16 + round(cos(i/steps*2*pi)*((1 << 15) - 1))) & 0xffff
                for i in range(steps)]
        samples = [Signal(16) for i in range(4)]
        for phase, sample in zip(phases, samples):
            table = Memory(16, steps, init=data)
            table_port = table.get_port(clock_domain="rtio")
            self.specials += table, table_port
            self.comb += [
                table_port.adr.eq(phase >> (len(self.coarse_ts) - resolution)),
                sample.eq(table_port.dat_r)
            ]

        self.sync.rtio += [sink.eq(Cat(samples))
                           for sink in self.jesd.core.sink.flatten()]


class Satellite(SatelliteBase):
    """
    DRTIO satellite with local DAC/SAWG channels, as well as TTL channels via FMC and VHDCI carrier.
    """
    def __init__(self, jdcg_type, ttlout=False, mcx_sqwave=False, **kwargs):
        SatelliteBase.__init__(self, identifier_suffix="." + jdcg_type, **kwargs)

        platform = self.platform

        self.submodules += RTMUARTForward(platform)

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

        self.rtio_channels = rtio_channels = []
        for i in range(4):
            phy = ttl_simple.Output(platform.request("user_led", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))
        for i in range(2):
            mcx_io = platform.request("mcx_io", i)
            if mcx_sqwave:
                phy = ttl_serdes_ultrascale.CustomOutput(4, mcx_io.level,
                    driver_type="square_wave",
                    rtio_freq=self.rtio_clk_freq,
                    wave_freq=9e6)
                self.comb += mcx_io.direction.eq(1)
            elif ttlout:
                phy = ttl_serdes_ultrascale.Output(4, mcx_io.level)
                self.comb += mcx_io.direction.eq(1)
            else:
                phy = ttl_serdes_ultrascale.InOut(4, mcx_io.level)
                self.comb += mcx_io.direction.eq(phy.oe)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        self.submodules.jesd_crg = jesd204_tools.UltrascaleCRG(platform)
        cls = {
            "sawg": JDCGSAWG,
            "pattern": JDCGPattern,
            "syncdds": JDCGSyncDDS
        }[jdcg_type]
        self.submodules.jdcg_0 = cls(platform, self.crg, self.jesd_crg, 0)
        self.submodules.jdcg_1 = cls(platform, self.crg, self.jesd_crg, 1)
        self.csr_devices.append("jesd_crg")
        self.csr_devices.append("jdcg_0")
        self.csr_devices.append("jdcg_1")
        self.config["HAS_JDCG"] = None
        self.add_csr_group("jdcg", ["jdcg_0", "jdcg_1"])
        self.config["RTIO_FIRST_SAWG_CHANNEL"] = len(rtio_channels)
        rtio_channels.extend(rtio.Channel.from_phy(phy)
                                for sawg in self.jdcg_0.sawgs +
                                            self.jdcg_1.sawgs
                                for phy in sawg.phys)

        # FMC-VHDCI-EEM DIOs x 2 (all OUTPUTs)
        platform.add_connectors(fmcdio_vhdci_eem.connectors)
        output_4x = partial(ttl_serdes_ultrascale.Output, 4)
        eem.DIO.add_std(self, 0,
            output_4x, output_4x,
            iostandard=lambda eem: IOStandard("LVDS"))
        eem.DIO.add_std(self, 1,
            output_4x, output_4x,
            iostandard=lambda eem: IOStandard("LVDS"))
        # FMC-DIO-32ch-LVDS-a Direction Control Pins (via shift register) as TTLs x 3
        platform.add_extension(fmcdio_vhdci_eem.io)
        print("fmcdio_vhdci_eem.[CLK, SER, LATCH] starting at RTIO channel 0x{:06x}"
              .format(len(rtio_channels)))
        fmcdio_dirctl = platform.request("fmcdio_dirctl", 0)
        fmcdio_dirctl_phys = [
            ttl_simple.Output(fmcdio_dirctl.clk),
            ttl_simple.Output(fmcdio_dirctl.ser),
            ttl_simple.Output(fmcdio_dirctl.latch)
        ]
        for phy in fmcdio_dirctl_phys:
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))
        workaround_us_lvds_tristate(platform)

        self.add_rtio(rtio_channels)

        self.submodules.sysref_sampler = jesd204_tools.SysrefSampler(
            platform.request("amc_fpga_sysref", 0), self.rtio_tsc.coarse_ts)
        self.csr_devices.append("sysref_sampler")
        self.jdcg_0.jesd.core.register_jref(self.sysref_sampler.jref)
        self.jdcg_1.jesd.core.register_jref(self.sysref_sampler.jref)
        if jdcg_type == "syncdds":
            self.comb += [
                self.jdcg_0.coarse_ts.eq(self.rtio_tsc.coarse_ts),
                self.jdcg_1.coarse_ts.eq(self.rtio_tsc.coarse_ts),
            ]


class SimpleSatellite(SatelliteBase):
    def __init__(self, **kwargs):
        SatelliteBase.__init__(self, **kwargs)

        platform = self.platform

        self.submodules += RTMUARTForward(platform)

        rtio_channels = []
        for i in range(4):
            phy = ttl_simple.Output(platform.request("user_led", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))
        mcx_io = platform.request("mcx_io", 0)
        phy = ttl_serdes_ultrascale.InOut(4, mcx_io.level)
        self.comb += mcx_io.direction.eq(phy.oe)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))
        mcx_io = platform.request("mcx_io", 1)
        phy = ttl_serdes_ultrascale.InOut(4, mcx_io.level)
        self.comb += mcx_io.direction.eq(phy.oe)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))

        self.add_rtio(rtio_channels)


def main():
    parser = argparse.ArgumentParser(
        description="Sayma AMC gateware and firmware builder")
    builder_args(parser)
    soc_sayma_amc_args(parser)
    parser.set_defaults(output_dir="artiq_sayma")
    parser.add_argument("-V", "--variant", default="satellite",
        help="variant: satellite/simplesatellite "
             "(default: %(default)s)")
    parser.add_argument("--sfp", default=False, action="store_true",
        help="use SFP port for DRTIO instead of uTCA backplane")
    parser.add_argument("--rtm-csr-csv",
        default=os.path.join("artiq_sayma", "rtm_gateware", "rtm_csr.csv"),
        help="CSV file listing remote CSRs on RTM (default: %(default)s)")
    parser.add_argument("--jdcg-type",
        default="sawg",
        help="Change type of signal generator. This is used exclusively for "
             "development and debugging.")
    parser.add_argument("--ttlout", default=False, action="store_true",
        help="force only outputs on the MCX TTL IOs")
    parser.add_argument("--mcx-sqwave", default=False, action="store_true",
        help="generate a square wave on the MCX TTL IOs")
    parser.add_argument("--gateware-identifier-str", default=None,
                        help="Override ROM identifier")
    args = parser.parse_args()

    variant = args.variant.lower()
    if variant == "satellite":
        soc = Satellite(
            with_sfp=args.sfp,
            jdcg_type=args.jdcg_type,
            ttlout=args.ttlout,
            mcx_sqwave=args.mcx_sqwave,
            gateware_identifier_str=args.gateware_identifier_str,
            **soc_sayma_amc_argdict(args))
    elif variant == "simplesatellite":
        soc = SimpleSatellite(
            with_sfp=args.sfp,
            gateware_identifier_str=args.gateware_identifier_str,
            **soc_sayma_amc_argdict(args))
    else:
        raise SystemExit("Invalid variant (-V/--variant)")

    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
