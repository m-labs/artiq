from migen.build.generic_platform import *


papilio_adapter_io = [
    ("ext_led", 0, Pins("B:7"), IOStandard("LVTTL")),

    # to feed the 125 MHz clock (preferrably from DDS SYNC_CLK)
    # to the FPGA, use the xtrig pair.
    #
    # on papiliopro-adapter, xtrig (C:12) is connected to a GCLK
    #
    # on pipistrello, C:15 is the only GCLK in proximity, used as a button
    # input, BTN2/PMT2 in papiliopro-adapter
    # either improve the DDS box to feed 125MHz into the PMT2 pair, or:
    #
    # * disconnect C:15 from its periphery on the adapter board
    # * bridge C:15 to the xtrig output of the transciever
    # * optionally, disconnect C:12 from its periphery
    ("xtrig", 0, Pins("C:12"), IOStandard("LVTTL")),
    ("pmt", 0, Pins("C:13"), IOStandard("LVTTL")),
    ("pmt", 1, Pins("C:14"), IOStandard("LVTTL")),
    ("pmt", 2, Pins("C:15"), IOStandard("LVTTL")),  # rarely equipped

    ("ttl", 0, Pins("C:11"), IOStandard("LVTTL")),
    ("ttl", 1, Pins("C:10"), IOStandard("LVTTL")),
    ("ttl", 2, Pins("C:9"), IOStandard("LVTTL")),
    ("ttl", 3, Pins("C:8"), IOStandard("LVTTL")),
    ("ttl", 4, Pins("C:7"), IOStandard("LVTTL")),
    ("ttl", 5, Pins("C:6"), IOStandard("LVTTL")),
    ("ttl", 6, Pins("C:5"), IOStandard("LVTTL")),
    ("ttl", 7, Pins("C:4"), IOStandard("LVTTL")),
    ("ttl_l_tx_en", 0, Pins("A:9"), IOStandard("LVTTL")),

    ("ttl", 8, Pins("C:3"), IOStandard("LVTTL")),
    ("ttl", 9, Pins("C:2"), IOStandard("LVTTL")),
    ("ttl", 10, Pins("C:1"), IOStandard("LVTTL")),
    ("ttl", 11, Pins("C:0"), IOStandard("LVTTL")),
    ("ttl", 12, Pins("B:4"), IOStandard("LVTTL")),
    ("ttl", 13, Pins("A:11"), IOStandard("LVTTL")),
    ("ttl", 14, Pins("B:5"), IOStandard("LVTTL")),
    ("ttl", 15, Pins("A:10"), IOStandard("LVTTL")),
    ("ttl_h_tx_en", 0, Pins("B:6"), IOStandard("LVTTL")),

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
