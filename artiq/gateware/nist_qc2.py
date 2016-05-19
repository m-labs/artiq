import itertools

from migen.build.generic_platform import *


__all__ = ["fmc_adapter_io"]


ttl_pins = [
    "LA00_CC_P", "LA02_P", "LA00_CC_N", "LA02_N", "LA01_CC_P", "LA01_CC_N", "LA06_P", "LA06_N",
    "LA05_P", "LA05_N", "LA10_P", "LA09_P", "LA10_N", "LA09_N", "LA13_P", "LA14_P",
    "LA13_N", "LA14_N", "LA17_CC_P", "LA17_CC_N"
]


def get_fmc_adapter_io():
    ttl = itertools.count()
    dds = itertools.count()
    i2c_fmc = itertools.count()
    spi = itertools.count()
    clkout = itertools.count()

    r = []
    for connector in "LPC", "HPC":
        for ttl_pin in ttl_pins:
            r.append(("ttl", next(ttl),
                      Pins(connector + ":" + ttl_pin), IOStandard("LVTTL")))

        def FPins(s):
            return Pins(s.replace("FMC:", connector + ":"))
        r += [
            ("dds", next(dds),
                Subsignal("a", FPins("FMC:LA22_N FMC:LA21_P FMC:LA22_P FMC:LA19_N "
                                    "FMC:LA20_N FMC:LA19_P FMC:LA20_P")),
                Subsignal("d", FPins("FMC:LA15_N FMC:LA16_N FMC:LA15_P FMC:LA16_P "
                                    "FMC:LA11_N FMC:LA12_N FMC:LA11_P FMC:LA12_P "
                                    "FMC:LA07_N FMC:LA08_N FMC:LA07_P FMC:LA08_P "
                                    "FMC:LA04_N FMC:LA03_N FMC:LA04_P FMC:LA03_P")),
                Subsignal("sel_n", FPins("FMC:LA24_N FMC:LA29_P FMC:LA28_P FMC:LA29_N "
                                        "FMC:LA28_N FMC:LA31_P FMC:LA30_P FMC:LA31_N "
                                        "FMC:LA30_N FMC:LA33_P FMC:LA33_N FMC:LA32_P")),
                Subsignal("fud", FPins("FMC:LA21_N")),
                Subsignal("wr_n", FPins("FMC:LA24_P")),
                Subsignal("rd_n", FPins("FMC:LA25_N")),
                Subsignal("rst", FPins("FMC:LA25_P")),
                IOStandard("LVTTL"), Misc("DRIVE=24")),

            ("i2c_fmc", next(i2c_fmc),
                Subsignal("scl", FPins("FMC:IIC_SCL")),
                Subsignal("sda", FPins("FMC:IIC_SDA")),
                IOStandard("LVCMOS25")),

            ("clkout", next(clkout), FPins("FMC:CLK1_M2C_P"),
                IOStandard("LVTTL")),

            ("spi", next(spi),
                Subsignal("clk", FPins("FMC:LA18_CC_P")),
                Subsignal("mosi", FPins("FMC:LA18_CC_N")),
                Subsignal("miso", FPins("FMC:LA23_P")),
                Subsignal("cs_n", FPins("FMC:LA23_N")),
                IOStandard("LVTTL")),

            ("spi", next(spi),
                Subsignal("clk", FPins("FMC:LA27_P")),
                Subsignal("mosi", FPins("FMC:LA26_P")),
                Subsignal("miso", FPins("FMC:LA27_N")),
                Subsignal("cs_n", FPins("FMC:LA26_N")),
                IOStandard("LVTTL")),
        ]
    return r


fmc_adapter_io = get_fmc_adapter_io()
