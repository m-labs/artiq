from migen.build.generic_platform import *

# Single new backplane in LPC connector, KC705 board, NIST QC2
fmc_adapter_io = [
    ("ttl", 0, Pins("LPC:LA00_CC_P"), IOStandard("LVTTL")),
    ("ttl", 1, Pins("LPC:LA02_P"), IOStandard("LVTTL")),
    ("ttl", 2, Pins("LPC:LA00_CC_N"), IOStandard("LVTTL")),
    ("ttl", 3, Pins("LPC:LA02_N"), IOStandard("LVTTL")),
    ("ttl", 4, Pins("LPC:LA01_CC_P"), IOStandard("LVTTL")),
    ("ttl", 5, Pins("LPC:LA01_CC_N"), IOStandard("LVTTL")),
    ("ttl", 6, Pins("LPC:LA06_P"), IOStandard("LVTTL")),
    ("ttl", 7, Pins("LPC:LA06_N"), IOStandard("LVTTL")),
    ("ttl", 8, Pins("LPC:LA05_P"), IOStandard("LVTTL")),
    ("ttl", 9, Pins("LPC:LA05_N"), IOStandard("LVTTL")),
    ("ttl", 10, Pins("LPC:LA10_P"), IOStandard("LVTTL")),
    ("ttl", 11, Pins("LPC:LA09_P"), IOStandard("LVTTL")),
    ("ttl", 12, Pins("LPC:LA10_N"), IOStandard("LVTTL")),
    ("ttl", 13, Pins("LPC:LA09_N"), IOStandard("LVTTL")),
    ("ttl", 14, Pins("LPC:LA13_P"), IOStandard("LVTTL")),
    ("ttl", 15, Pins("LPC:LA14_P"), IOStandard("LVTTL")),
    ("ttl", 16, Pins("LPC:LA13_N"), IOStandard("LVTTL")),
    ("ttl", 17, Pins("LPC:LA14_N"), IOStandard("LVTTL")),
    ("ttl", 18, Pins("LPC:LA17_CC_P"), IOStandard("LVTTL")),
    ("ttl", 19, Pins("LPC:LA17_CC_N"), IOStandard("LVTTL")),
    ("ttl", 20, Pins("LPC:LA18_CC_P"), IOStandard("LVTTL")),
    ("ttl", 21, Pins("LPC:LA18_CC_N"), IOStandard("LVTTL")),
    ("ttl", 22, Pins("LPC:LA23_P"), IOStandard("LVTTL")),
    ("ttl", 23, Pins("LPC:LA23_N"), IOStandard("LVTTL")),
    ("ttl", 24, Pins("LPC:LA27_P"), IOStandard("LVTTL")),
    ("ttl", 25, Pins("LPC:LA26_P"), IOStandard("LVTTL")),
    ("ttl", 26, Pins("LPC:LA27_N"), IOStandard("LVTTL")),
    ("ttl", 27, Pins("LPC:LA26_N"), IOStandard("LVTTL")),


    ("dds", 0,
        Subsignal("a", Pins("LPC:LA22_N LPC:LA21_P LPC:LA22_P LPC:LA19_N "
                            "LPC:LA20_N LPC:LA19_P LPC:LA20_P")),
        Subsignal("d", Pins("LPC:LA15_N LPC:LA16_N LPC:LA15_P LPC:LA16_P "
                            "LPC:LA11_N LPC:LA12_N LPC:LA11_P LPC:LA12_P "
                            "LPC:LA07_N LPC:LA08_N LPC:LA07_P LPC:LA08_P "
                            "LPC:LA04_N LPC:LA03_N LPC:LA04_P LPC:LA03_P")),
        Subsignal("sel_n", Pins("LPC:LA24_N LPC:LA29_P LPC:LA28_P LPC:LA29_N "
                                "LPC:LA28_N LPC:LA31_P LPC:LA30_P LPC:LA31_N "
                                "LPC:LA30_N LPC:LA33_P LPC:LA33_N LPC:LA32_P")),
        Subsignal("fud", Pins("LPC:LA21_N")),
        Subsignal("wr_n", Pins("LPC:LA24_P")),
        Subsignal("rd_n", Pins("LPC:LA25_N")),
        Subsignal("rst", Pins("LPC:LA25_P")),
        IOStandard("LVTTL")),

    ("i2c", 0,
        Subsignal("scl", Pins("LPC:IIC_SCL")),
        Subsignal("sda", Pins("LPC:IIC_SDA")),
        IOStandard("LVCMOS25")),

    ("clk_m2c", 0,
        Subsignal("p", Pins("LPC:CLK0_M2C_P")),
        Subsignal("n", Pins("LPC:CLK0_M2C_N")),
        IOStandard("LVDS")),

    ("clk_m2c", 1,
        Subsignal("p", Pins("LPC:CLK1_M2C_P")),
        Subsignal("n", Pins("LPC:CLK1_M2C_N")),
        IOStandard("LVDS")),

]
