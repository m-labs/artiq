#!/usr/bin/env python3

import argparse

from misoc.targets.efc import BaseSoC
from misoc.integration.builder import builder_args, builder_argdict

from artiq.build_soc import *

class Satellite(BaseSoC):
    def __init__(self, rtio_clk_freq=125e6, hw_rev="v1.0", **kwargs):
        cpu_bus_width = 64
        BaseSoC.__init__(self,
                 cpu_type="vexriscv",
                 cpu_bus_width=cpu_bus_width,
                 sdram_controller_type="minicon",
                 l2_size=128*1024,
                 clk_freq=rtio_clk_freq,
                 **kwargs)
        add_identifier(self, gateware_identifier_str=None)

        self.config["DRTIO_ROLE"] = "satellite"

        # Hardware Modules to be added

def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder for EEM FMC Carrier systems")
    builder_args(parser)
    parser.set_defaults(output_dir="artiq_efc")
    parser.set_defaults(variant='satellite')
    args = parser.parse_args()

    argdict = dict()

    soc = Satellite(**argdict)
    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
