#!/usr/bin/env python3.5

import argparse

from migen import *

from misoc.targets.kc705 import MiniSoC, soc_kc705_args, soc_kc705_argdict
from misoc.integration.builder import builder_args, builder_argdict

from artiq.gateware.soc import AMPSoC, build_artiq_soc
from artiq.gateware.drtio.transceiver import gtx_7series
from artiq.gateware.drtio import DRTIOMaster
from artiq import __version__ as artiq_version


class Master(MiniSoC, AMPSoC):
    mem_map = {
        "timer_kernel":  0x10000000, # (shadow @0x90000000)
        "drtio":         0x20000000, # (shadow @0xa0000000)
        "mailbox":       0x70000000  # (shadow @0xf0000000)
    }
    mem_map.update(MiniSoC.mem_map)

    def __init__(self, **kwargs):
        MiniSoC.__init__(self,
                         cpu_type="or1k",
                         sdram_controller_type="minicon",
                         l2_size=128*1024,
                         with_timer=False,
                         ident=artiq_version,
                         **kwargs)
        AMPSoC.__init__(self)

        platform = self.platform

        self.comb += platform.request("sfp_tx_disable_n").eq(1)
        self.submodules.transceiver = gtx_7series.GTX_1000BASE_BX10(
            clock_pads=platform.request("sgmii_clock"),
            tx_pads=platform.request("sfp_tx"),
            rx_pads=platform.request("sfp_rx"),
            sys_clk_freq=self.clk_freq,
            clock_div2=True)
        self.submodules.drtio = DRTIOMaster(self.transceiver)
        self.register_kernel_cpu_csrdevice("drtio")


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ with DRTIO on KC705 - Master")
    builder_args(parser)
    soc_kc705_args(parser)
    args = parser.parse_args()

    soc = Master(**soc_kc705_argdict(args))
    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
