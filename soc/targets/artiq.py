from migen.fhdl.std import *
from mibuild.generic_platform import *

from misoclib import gpio
from targets.ppro import BaseSoC

from artiqlib import rtio, ad9858

_tester_io = [
    ("user_led", 1, Pins("B:7"), IOStandard("LVTTL")),
    ("ttl", 0, Pins("C:13"), IOStandard("LVTTL")),
    ("ttl", 1, Pins("C:11"), IOStandard("LVTTL")),
    ("ttl", 2, Pins("C:10"), IOStandard("LVTTL")),
    ("ttl", 3, Pins("C:9"), IOStandard("LVTTL")),
    ("ttl_tx_en", 0, Pins("A:9"), IOStandard("LVTTL")),
    ("dds", 0,
        Subsignal("a", Pins("A:5 B:10 A:6 B:9 A:7 B:8")),
        Subsignal("d", Pins("A:12 B:3 A:13 B:2 A:14 B:1 A:15 B:0")),
        Subsignal("sel", Pins("A:2 B:14 A:1 B:15 A:0")),
        Subsignal("p", Pins("A:8 B:12")),
        Subsignal("fud_n", Pins("B:11")),
        Subsignal("wr_n", Pins("A:4")),
        Subsignal("rd_n", Pins("B:13")),
        Subsignal("rst_n", Pins("A:3")),
        IOStandard("LVTTL")),
]

class ARTIQMiniSoC(BaseSoC):
    csr_map = {
        "rtio":            10
    }
    csr_map.update(BaseSoC.csr_map)

    def __init__(self, platform, cpu_type="or1k", **kwargs):
        BaseSoC.__init__(self, platform, cpu_type=cpu_type, **kwargs)
        platform.add_extension(_tester_io)

        self.submodules.leds = gpio.GPIOOut(Cat(platform.request("user_led", 0),
            platform.request("user_led", 1)))

        self.comb += platform.request("ttl_tx_en").eq(1)
        rtio_pads = [platform.request("ttl", i) for i in range(4)]
        self.submodules.rtiophy = rtio.phy.SimplePHY(rtio_pads,
            {rtio_pads[1], rtio_pads[2], rtio_pads[3]})
        self.submodules.rtio = rtio.RTIO(self.rtiophy)

        self.submodules.dds = ad9858.AD9858(platform.request("dds"))
        self.add_wb_slave(lambda a: a[26:29] == 3, self.dds.bus)

default_subtarget = ARTIQMiniSoC
