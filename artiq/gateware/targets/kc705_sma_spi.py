#!/usr/bin/env python3

import argparse

from migen import *

from migen.build.generic_platform import *
from misoc.targets.kc705 import soc_kc705_args, soc_kc705_argdict
from misoc.integration.builder import builder_args, builder_argdict

from artiq.gateware.amp import build_artiq_soc
from artiq.gateware import rtio
from artiq.gateware.rtio.phy import ttl_simple, spi


from .kc705_dds import _NIST_Ions


_sma_spi = [
    ("sma_spi", 0,
        Subsignal("clk", Pins("Y23")),  # user_sma_gpio_p
        Subsignal("cs_n", Pins("Y24")),  # user_sma_gpio_n
        Subsignal("mosi", Pins("L25")),  # user_sma_clk_p
        Subsignal("miso", Pins("K25")),  # user_sma_clk_n
        IOStandard("LVCMOS33")),
]


class SMA_SPI(_NIST_Ions):
    """
    SPI on 4 SMA for PDQ2 test/demo.
    """
    def __init__(self, cpu_type="or1k", **kwargs):
        _NIST_Ions.__init__(self, cpu_type, **kwargs)

        platform = self.platform
        self.platform.add_extension(_sma_spi)

        rtio_channels = []

        phy = ttl_simple.Output(platform.request("user_led", 2))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))

        ams101_dac = self.platform.request("ams101_dac", 0)
        phy = ttl_simple.Output(ams101_dac.ldac)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))

        phy = spi.SPIMaster(ams101_dac)
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(
            phy, ofifo_depth=4, ififo_depth=4))

        phy = spi.SPIMaster(self.platform.request("sma_spi"))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(
            phy, ofifo_depth=128, ififo_depth=128))

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.LogChannel())

        self.add_rtio(rtio_channels)


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder / "
        "KC705 SMA SPI demo/test for PDQ2")
    builder_args(parser)
    soc_kc705_args(parser)
    args = parser.parse_args()

    soc = SMA_SPI(**soc_kc705_argdict(args))
    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
