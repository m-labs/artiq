from migen.build.generic_platform import *

from artiq.coredevice.fmcdio_vhdci_eem import *


io = [
    ("fmcdio_dirctl", 0,
        Subsignal("clk", Pins("LPC:LA32_N")),
        Subsignal("ser", Pins("LPC:LA33_P")),
        Subsignal("latch", Pins("LPC:LA32_P")),
        IOStandard("LVCMOS18")
    ),
]

def _get_connectors():
    connectors = []
    for i in range(4):
        connections = dict()
        for j, pair in enumerate(eem_fmc_connections[i]):
            for pn in "n", "p":
                cc = "cc_" if j == 0 else ""
                connections["d{}_{}{}".format(j, cc, pn)] = \
                    "LPC:LA{:02d}_{}{}".format(pair, cc.upper(), pn.upper())
        connectors.append(("eem{}".format(i), connections))
    return connectors


connectors = _get_connectors()
