#!/usr/bin/env python3

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.build.platforms.sinara import sayma_rtm

from misoc.interconnect import wishbone, stream

from artiq.gateware import serwb


class CRG(Module):
    def __init__(self, platform):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_clk200 = ClockDomain()

        clk50 = platform.request("clk50")
        self.reset = Signal()

        pll_locked = Signal()
        pll_fb = Signal()
        pll_sys = Signal()
        pll_clk200 = Signal()
        self.specials += [
            Instance("PLLE2_BASE",
                     p_STARTUP_WAIT="FALSE", o_LOCKED=pll_locked,

                     # VCO @ 1GHz
                     p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=20.0,
                     p_CLKFBOUT_MULT=20, p_DIVCLK_DIVIDE=1,
                     i_CLKIN1=clk50, i_CLKFBIN=pll_fb, o_CLKFBOUT=pll_fb,

                     # 125MHz
                     p_CLKOUT0_DIVIDE=8, p_CLKOUT0_PHASE=0.0, o_CLKOUT0=pll_sys,

                     # 200MHz
                     p_CLKOUT3_DIVIDE=5, p_CLKOUT3_PHASE=0.0, o_CLKOUT3=pll_clk200
            ),
            Instance("BUFG", i_I=pll_sys, o_O=self.cd_sys.clk),
            Instance("BUFG", i_I=pll_clk200, o_O=self.cd_clk200.clk),
            AsyncResetSynchronizer(self.cd_sys, ~pll_locked | self.reset),
            AsyncResetSynchronizer(self.cd_clk200, ~pll_locked | self.reset)
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


class SaymaRTM(Module):
    def __init__(self, platform):
        self.submodules.crg = CRG(platform)
        self.crg.cd_sys.clk.attr.add("keep")
        clk_freq = 125e6
        platform.add_period_constraint(self.crg.cd_sys.clk, 8.0)

        sram = wishbone.SRAM(8192, init=[0x12345678, 0xbadc0f33, 0xabad1dea, 0xdeadbeef])
        self.submodules += sram

        # TODO: push all those serwb bits into library modules
        # maybe keep only 3 user-visible modules: serwb PLL, serwb PHY, and serwb core
        # TODO: after this is done, stop exposing internal modules in serwb/__init__.py
        # TODO: avoid having a "serdes" clock domain at the top level, rename to "serwb_serdes" or similar.

        # serwb SERDES
        serwb_pll = serwb.s7phy.S7SerdesPLL(125e6, 1.25e9, vco_div=1)
        self.submodules += serwb_pll

        serwb_serdes = serwb.s7phy.S7Serdes(serwb_pll, platform.request("amc_rtm_serwb"), mode="slave")
        self.submodules += serwb_serdes
        serwb_init = serwb.phy.SerdesSlaveInit(serwb_serdes, taps=32)
        self.submodules += serwb_init
        serwb_control = serwb.phy.SerdesControl(serwb_init, mode="slave")
        self.submodules += serwb_control
        self.comb += self.crg.reset.eq(serwb_init.reset)

        serwb_serdes.cd_serdes.clk.attr.add("keep")
        serwb_serdes.cd_serdes_20x.clk.attr.add("keep")
        serwb_serdes.cd_serdes_5x.clk.attr.add("keep")
        platform.add_period_constraint(serwb_serdes.cd_serdes.clk, 32.0),
        platform.add_period_constraint(serwb_serdes.cd_serdes_20x.clk, 1.6),
        platform.add_period_constraint(serwb_serdes.cd_serdes_5x.clk, 6.4)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            serwb_serdes.cd_serdes.clk,
            serwb_serdes.cd_serdes_5x.clk)

        # serwb master
        serwb_depacketizer = serwb.packet.Depacketizer(int(clk_freq))
        serwb_packetizer = serwb.packet.Packetizer()
        self.submodules += serwb_depacketizer, serwb_packetizer
        serwb_etherbone = serwb.etherbone.Etherbone(mode="master")
        self.submodules += serwb_etherbone
        serwb_tx_cdc = ClockDomainsRenamer({"write": "sys", "read": "serdes"})(
            stream.AsyncFIFO([("data", 32)], 8))
        self.submodules += serwb_tx_cdc
        serwb_rx_cdc = ClockDomainsRenamer({"write": "serdes", "read": "sys"})(
            stream.AsyncFIFO([("data", 32)], 8))
        self.submodules += serwb_rx_cdc
        self.comb += [
            # core <--> etherbone
            serwb_depacketizer.source.connect(serwb_etherbone.sink),
            serwb_etherbone.source.connect(serwb_packetizer.sink),

            # core --> serdes
            serwb_packetizer.source.connect(serwb_tx_cdc.sink),
            If(serwb_tx_cdc.source.stb & serwb_init.ready,
                serwb_serdes.tx_data.eq(serwb_tx_cdc.source.data)
            ),
            serwb_tx_cdc.source.ack.eq(serwb_init.ready),

            # serdes --> core
            serwb_rx_cdc.sink.stb.eq(serwb_init.ready),
            serwb_rx_cdc.sink.data.eq(serwb_serdes.rx_data),
            serwb_rx_cdc.source.connect(serwb_depacketizer.sink),
        ]

        # connect serwb to SRAM
        self.comb += serwb_etherbone.wishbone.bus.connect(sram.bus)


def main():
    platform = sayma_rtm.Platform()
    top = SaymaRTM(platform)
    platform.build(top, build_dir="artiq_sayma_rtm")


if __name__ == "__main__":
    main()
