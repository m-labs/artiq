#!/usr/bin/env python3

import argparse
import os
import subprocess
import struct

from migen import *
from migen.genlib.cdc import MultiReg

from misoc.interconnect.csr import *
from misoc.cores import gpio
from misoc.cores import spi2
from misoc.cores.a7_gtp import *
from misoc.targets.sayma_rtm import BaseSoC, soc_sayma_rtm_args, soc_sayma_rtm_argdict
from misoc.integration.builder import Builder, builder_args, builder_argdict

from artiq.gateware import rtio
from artiq.gateware.rtio.phy import ttl_simple, ttl_serdes_7series
from artiq.gateware.drtio.transceiver import gtp_7series
from artiq.gateware.drtio.siphaser import SiPhaser7Series
from artiq.gateware.drtio.wrpll import WRPLL, DDMTDSamplerGTP
from artiq.gateware.drtio.rx_synchronizer import XilinxRXSynchronizer
from artiq.gateware.drtio import *
from artiq.build_soc import add_identifier
from artiq import __artiq_dir__ as artiq_dir


def fix_serdes_timing_path(platform):
    # ignore timing of path from OSERDESE2 through the pad to ISERDESE2
    platform.add_platform_command(
        "set_false_path -quiet "
        "-through [get_pins -filter {{REF_PIN_NAME == OQ || REF_PIN_NAME == TQ}} "
            "-of [get_cells -filter {{REF_NAME == OSERDESE2}}]] "
        "-to [get_pins -filter {{REF_PIN_NAME == D}} "
            "-of [get_cells -filter {{REF_NAME == ISERDESE2}}]]"
    )


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


class _SatelliteBase(BaseSoC):
    mem_map = {
        "drtioaux": 0x50000000,
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, rtio_clk_freq, *, with_wrpll, **kwargs):
        BaseSoC.__init__(self,
                 cpu_type="or1k",
                 **kwargs)
        add_identifier(self)
        self.rtio_clk_freq = rtio_clk_freq

        platform = self.platform

        disable_cdrclkc_ibuf = Signal(reset=1)
        disable_cdrclkc_ibuf.attr.add("no_retiming")
        cdrclkc_clkout = platform.request("cdr_clk_clean")
        cdrclkc_clkout_buf = Signal()
        self.specials += Instance("IBUFDS_GTE2",
            i_CEB=disable_cdrclkc_ibuf,
            i_I=cdrclkc_clkout.p, i_IB=cdrclkc_clkout.n,
            o_O=cdrclkc_clkout_buf)
        qpll_drtio_settings = QPLLSettings(
            refclksel=0b001,
            fbdiv=4,
            fbdiv_45=5,
            refclk_div=1)
        qpll = QPLL(cdrclkc_clkout_buf, qpll_drtio_settings)
        self.submodules += qpll

        self.submodules.drtio_transceiver = gtp_7series.GTP(
            qpll_channel=qpll.channels[0],
            data_pads=[platform.request("rtm_amc_link", 0)],
            sys_clk_freq=self.clk_freq,
            rtio_clk_freq=rtio_clk_freq)
        self.csr_devices.append("drtio_transceiver")
        self.sync += disable_cdrclkc_ibuf.eq(
            ~self.drtio_transceiver.stable_clkin.storage)

        self.submodules.rtio_tsc = rtio.TSC("sync", glbl_fine_ts_width=3)

        cdr = ClockDomainsRenamer({"rtio_rx": "rtio_rx0"})

        self.submodules.rx_synchronizer = cdr(XilinxRXSynchronizer())
        core = cdr(DRTIOSatellite(
            self.rtio_tsc, self.drtio_transceiver.channels[0],
            self.rx_synchronizer))
        self.submodules.drtiosat = core
        self.csr_devices.append("drtiosat")

        coreaux = cdr(DRTIOAuxController(core.link_layer))
        self.submodules.drtioaux0 = coreaux
        self.csr_devices.append("drtioaux0")

        memory_address = self.mem_map["drtioaux"]
        self.add_wb_slave(memory_address, 0x800,
                          coreaux.bus)
        self.add_memory_region("drtioaux0_mem", memory_address | self.shadow_base, 0x800)

        self.config["HAS_DRTIO"] = None
        self.add_csr_group("drtioaux", ["drtioaux0"])
        self.add_memory_group("drtioaux_mem", ["drtioaux0_mem"])

        gtp = self.drtio_transceiver.gtps[0]
        rtio_clk_period = 1e9/rtio_clk_freq
        self.config["RTIO_FREQUENCY"] = str(rtio_clk_freq/1e6)
        if with_wrpll:
            self.comb += [
                platform.request("filtered_clk_sel").eq(0),
                platform.request("ddmtd_main_dcxo_oe").eq(1),
                platform.request("ddmtd_helper_dcxo_oe").eq(1)
            ]
            self.submodules.wrpll_sampler = DDMTDSamplerGTP(
                self.drtio_transceiver,
                platform.request("cdr_clk_clean_fabric"))
            self.submodules.wrpll = WRPLL(
                helper_clk_pads=platform.request("ddmtd_helper_clk"),
                main_dcxo_i2c=platform.request("ddmtd_main_dcxo_i2c"),
                helper_dxco_i2c=platform.request("ddmtd_helper_dcxo_i2c"),
                ddmtd_inputs=self.wrpll_sampler)
            self.csr_devices.append("wrpll")
            platform.add_period_constraint(self.wrpll.cd_helper.clk, rtio_clk_period*0.99)
            platform.add_false_path_constraints(self.crg.cd_sys.clk, self.wrpll.cd_helper.clk)
            platform.add_false_path_constraints(self.wrpll.cd_helper.clk, gtp.rxoutclk)
        else:
            self.comb += platform.request("filtered_clk_sel").eq(1)
            self.submodules.siphaser = SiPhaser7Series(
                si5324_clkin=platform.request("si5324_clkin"),
                rx_synchronizer=self.rx_synchronizer,
                ref_clk=self.crg.cd_sys.clk, ref_div2=True,
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

        platform.add_period_constraint(gtp.txoutclk, rtio_clk_period)
        platform.add_period_constraint(gtp.rxoutclk, rtio_clk_period)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            gtp.txoutclk, gtp.rxoutclk)

        self.submodules.rtio_crg = _RTIOClockMultiplier(rtio_clk_freq)
        self.csr_devices.append("rtio_crg")
        fix_serdes_timing_path(platform)

    def add_rtio(self, rtio_channels):
        self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)
        self.csr_devices.append("rtio_moninj")

        self.submodules.local_io = SyncRTIO(self.rtio_tsc, rtio_channels)
        self.comb += self.drtiosat.async_errors.eq(self.local_io.async_errors)
        self.comb += self.drtiosat.cri.connect(self.local_io.cri)


class Satellite(_SatelliteBase):
    def __init__(self, **kwargs):
        _SatelliteBase.__init__(self, **kwargs)

        platform = self.platform

        rtio_channels = []
        for bm in range(2):
            print("BaseMod{} RF switches starting at RTIO channel 0x{:06x}"
                .format(bm, len(rtio_channels)))
            for i in range(4):
                phy = ttl_serdes_7series.Output_8X(platform.request("basemod{}_rfsw".format(bm), i),
                    invert=True)
                self.submodules += phy
                rtio_channels.append(rtio.Channel.from_phy(phy))

            print("BaseMod{} attenuator starting at RTIO channel 0x{:06x}"
                .format(bm, len(rtio_channels)))
            basemod_att = platform.request("basemod{}_att".format(bm))
            for name in "rst_n clk le".split():
                signal = getattr(basemod_att, name)
                for i in range(len(signal)):
                    phy = ttl_simple.Output(signal[i])
                    self.submodules += phy
                    rtio_channels.append(rtio.Channel.from_phy(phy))
            phy = ttl_simple.Output(basemod_att.mosi[0])
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))
            for i in range(3):
                self.comb += basemod_att.mosi[i+1].eq(basemod_att.miso[i])
            phy = ttl_simple.InOut(basemod_att.miso[3])
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        self.add_rtio(rtio_channels)

        self.comb += platform.request("clk_src_ext_sel").eq(0)

        # HMC clock chip and DAC control
        self.comb += [
            platform.request("ad9154_rst_n", 0).eq(1),
            platform.request("ad9154_rst_n", 1).eq(1)
        ]
        self.submodules.converter_spi = spi2.SPIMaster(spi2.SPIInterface(
            platform.request("hmc_spi"),
            platform.request("ad9154_spi", 0),
            platform.request("ad9154_spi", 1)))
        self.csr_devices.append("converter_spi")
        self.submodules.hmc7043_reset = gpio.GPIOOut(
            platform.request("hmc7043_reset"), reset_out=1)
        self.csr_devices.append("hmc7043_reset")
        self.submodules.hmc7043_gpo = gpio.GPIOIn(
            platform.request("hmc7043_gpo"))
        self.csr_devices.append("hmc7043_gpo")
        self.config["HAS_HMC830_7043"] = None
        self.config["HAS_AD9154"] = None
        self.config["AD9154_COUNT"] = 2
        self.config["CONVERTER_SPI_HMC830_CS"] = 0
        self.config["CONVERTER_SPI_HMC7043_CS"] = 1
        self.config["CONVERTER_SPI_FIRST_AD9154_CS"] = 2
        self.config["HMC830_REF"] = str(int(self.rtio_clk_freq/1e6))

        # HMC workarounds
        self.comb += platform.request("hmc830_pwr_en").eq(1)
        self.submodules.hmc7043_out_en = gpio.GPIOOut(
            platform.request("hmc7043_out_en"))
        self.csr_devices.append("hmc7043_out_en")


class SatmanSoCBuilder(Builder):
    def __init__(self, *args, **kwargs):
        Builder.__init__(self, *args, **kwargs)
        firmware_dir = os.path.join(artiq_dir, "firmware")
        self.software_packages = []
        self.add_software_package("satman", os.path.join(firmware_dir, "satman"))

    def initialize_memory(self):
        satman = os.path.join(self.output_dir, "software", "satman",
                              "satman.bin")
        with open(satman, "rb") as boot_file:
            boot_data = []
            unpack_endian = ">I"
            while True:
                w = boot_file.read(4)
                if not w:
                    break
                boot_data.append(struct.unpack(unpack_endian, w)[0])

        self.soc.main_ram.mem.init = boot_data


def main():
    parser = argparse.ArgumentParser(
        description="Sayma RTM gateware and firmware builder")
    builder_args(parser)
    soc_sayma_rtm_args(parser)
    parser.add_argument("--rtio-clk-freq",
        default=150, type=int, help="RTIO clock frequency in MHz")
    parser.add_argument("--with-wrpll", default=False, action="store_true")
    parser.set_defaults(output_dir=os.path.join("artiq_sayma", "rtm"))
    args = parser.parse_args()

    soc = Satellite(
        rtio_clk_freq=1e6*args.rtio_clk_freq, with_wrpll=args.with_wrpll,
        **soc_sayma_rtm_argdict(args))
    builder = SatmanSoCBuilder(soc, **builder_argdict(args))
    try:
        builder.build()
    except subprocess.CalledProcessError as e:
        raise SystemExit("Command {} failed".format(" ".join(e.cmd)))


if __name__ == "__main__":
    main()
