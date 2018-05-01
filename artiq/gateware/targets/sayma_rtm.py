#!/usr/bin/env python3

import os
import argparse

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.build.platforms.sinara import sayma_rtm

from misoc.interconnect import wishbone, stream
from misoc.interconnect.csr import *
from misoc.cores import identifier
from misoc.cores import spi2
from misoc.cores import gpio
from misoc.integration.wb_slaves import WishboneSlaveManager
from misoc.integration.cpu_interface import get_csr_csv

from artiq.gateware import serwb
from artiq import __version__ as artiq_version


class CRG(Module):
    def __init__(self, platform):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sys4x = ClockDomain(reset_less=True)
        self.clock_domains.cd_clk200 = ClockDomain()

        self.serwb_refclk = Signal()
        self.serwb_reset = Signal()

        pll_locked = Signal()
        pll_fb = Signal()
        pll_sys4x = Signal()
        pll_clk200 = Signal()
        self.specials += [
            Instance("MMCME2_BASE",
                p_STARTUP_WAIT="FALSE", o_LOCKED=pll_locked,

                # VCO @ 1GHz
                p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=10.0,
                p_CLKFBOUT_MULT_F=10, p_DIVCLK_DIVIDE=1,
                i_CLKIN1=self.serwb_refclk, i_CLKFBIN=pll_fb, o_CLKFBOUT=pll_fb,

                # 500MHz
                p_CLKOUT0_DIVIDE_F=2, p_CLKOUT0_PHASE=0.0, o_CLKOUT0=pll_sys4x,

                # 200MHz
                p_CLKOUT1_DIVIDE=5, p_CLKOUT1_PHASE=0.0, o_CLKOUT1=pll_clk200
            ),
            Instance("BUFR", p_BUFR_DIVIDE="4", i_I=pll_sys4x, o_O=self.cd_sys.clk),
            Instance("BUFIO", i_I=pll_sys4x, o_O=self.cd_sys4x.clk),
            Instance("BUFG", i_I=pll_clk200, o_O=self.cd_clk200.clk),
            AsyncResetSynchronizer(self.cd_sys, ~pll_locked | self.serwb_reset),
            AsyncResetSynchronizer(self.cd_clk200, ~pll_locked | self.serwb_reset)
        ]

        reset_counter = Signal(4, reset=15)
        ic_reset = Signal(reset=1)
        self.sync.clk200 += \
            If(reset_counter != 0,
                reset_counter.eq(reset_counter - 1)
            ).Else(
                ic_reset.eq(0)
            )
        self.specials += Instance("IDELAYCTRL", i_REFCLK=ClockSignal("clk200"), i_RST=ic_reset)


class RTMMagic(Module, AutoCSR):
    def __init__(self):
        self.magic = CSRStatus(32)
        self.comb += self.magic.status.eq(0x5352544d)  # "SRTM"


CSR_RANGE_SIZE = 0x800


class SaymaRTM(Module):
    def __init__(self, platform):
        csr_devices = []

        self.submodules.crg = CRG(platform)
        clk_freq = 125e6

        self.submodules.rtm_magic = RTMMagic()
        csr_devices.append("rtm_magic")
        self.submodules.rtm_identifier = identifier.Identifier(artiq_version)
        csr_devices.append("rtm_identifier")

        # clock mux: 100MHz ext SMA clock to HMC830 input
        self.submodules.clock_mux = gpio.GPIOOut(Cat(
            platform.request("clk_src_ext_sel"),
            platform.request("ref_clk_src_sel"),
            platform.request("dac_clk_src_sel")))
        csr_devices.append("clock_mux")

        # UART loopback
        serial = platform.request("serial")
        self.comb += serial.tx.eq(serial.rx)

        # Allaki: enable RF output, GPIO access to attenuator
        self.comb += [
            platform.request("allaki0_rfsw0").eq(1),
            platform.request("allaki0_rfsw1").eq(1),
            platform.request("allaki1_rfsw0").eq(1),
            platform.request("allaki1_rfsw1").eq(1),
            platform.request("allaki2_rfsw0").eq(1),
            platform.request("allaki2_rfsw1").eq(1),
            platform.request("allaki3_rfsw0").eq(1),
            platform.request("allaki3_rfsw1").eq(1),
        ]
        allaki_atts = [
            platform.request("allaki0_att0"),
            platform.request("allaki0_att1"),
            platform.request("allaki1_att0"),
            platform.request("allaki1_att1"),
            platform.request("allaki2_att0"),
            platform.request("allaki2_att1"),
            platform.request("allaki3_att0"),
            platform.request("allaki3_att1"),
        ]
        allaki_att_gpio = []
        for allaki_att in allaki_atts:
            allaki_att_gpio += [
                allaki_att.le,
                allaki_att.sin,
                allaki_att.clk,
                allaki_att.rst_n,
            ]
        self.submodules.allaki_atts = gpio.GPIOOut(Cat(*allaki_att_gpio))
        csr_devices.append("allaki_atts")

        # HMC clock chip and DAC control
        self.comb += [
            platform.request("ad9154_rst_n").eq(1),
            platform.request("ad9154_txen", 0).eq(0b11),
            platform.request("ad9154_txen", 1).eq(0b11)
        ]

        self.submodules.converter_spi = spi2.SPIMaster(spi2.SPIInterface(
            platform.request("hmc_spi"),
            platform.request("ad9154_spi", 0),
            platform.request("ad9154_spi", 1)))
        csr_devices.append("converter_spi")
        self.comb += platform.request("hmc7043_reset").eq(0)

        # AMC/RTM serwb
        serwb_pads = platform.request("amc_rtm_serwb")
        platform.add_period_constraint(serwb_pads.clk_p, 10.)
        serwb_phy_rtm = serwb.phy.SERWBPHY(platform.device, serwb_pads, mode="slave")
        self.submodules.serwb_phy_rtm = serwb_phy_rtm
        self.comb += [
            self.crg.serwb_refclk.eq(serwb_phy_rtm.serdes.refclk),
            self.crg.serwb_reset.eq(serwb_phy_rtm.serdes.reset)
        ]
        csr_devices.append("serwb_phy_rtm")

        serwb_core = serwb.core.SERWBCore(serwb_phy_rtm, int(clk_freq), mode="master")
        self.submodules += serwb_core

        # process CSR devices and connect them to serwb
        self.csr_regions = []
        wb_slaves = WishboneSlaveManager(0x10000000)
        for i, name in enumerate(csr_devices):
            origin = i*CSR_RANGE_SIZE
            module = getattr(self, name)
            csrs = module.get_csrs()

            bank = wishbone.CSRBank(csrs)
            self.submodules += bank

            wb_slaves.add(origin, CSR_RANGE_SIZE, bank.bus)
            self.csr_regions.append((name, origin, 32, csrs))

        self.submodules += wishbone.Decoder(serwb_core.etherbone.wishbone.bus,
                                            wb_slaves.get_interconnect_slaves(),
                                            register=True)


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder for Kasli systems")
    parser.add_argument("--output-dir", default="artiq_sayma/rtm_gateware",
                        help="output directory for generated "
                             "source files and binaries")
    parser.add_argument("--no-compile-gateware", action="store_true",
                        help="do not compile the gateware, only generate "
                             "the CSR map")
    parser.add_argument("--csr-csv", default=None,
                        help="store CSR map in CSV format into the "
                             "specified file")
    args = parser.parse_args()

    platform = sayma_rtm.Platform()
    top = SaymaRTM(platform)

    os.makedirs(args.output_dir, exist_ok=True)
    with open(os.path.join(args.output_dir, "rtm_csr.csv"), "w") as f:
        f.write(get_csr_csv(top.csr_regions))

    if not args.no_compile_gateware:
        platform.build(top, build_dir=args.output_dir, build_name="rtm")


if __name__ == "__main__":
    main()
