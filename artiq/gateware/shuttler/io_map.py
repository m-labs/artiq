from copy import copy
import pprint
from migen import *
from migen.build.generic_platform import *

def default_iostandard():
    return IOStandard("LVDS_25")

def _fmc_pins(fmc, sigs_names):
    sig_list = sigs_names.split()
    temp = [("fmc{}:{}".format(fmc, sig)) for sig in sig_list]
    pins = temp.pop(0)
    for sig in temp:
        pins = "{} {}".format(pins, sig)
    return pins

class shuttler_fmc_ios():
    @staticmethod
    def fmc_io_map(fmc, iostandard):
        ios = []

        signal_dict_template = {"Pins": ""}
        dac_din_template = {"data": [], "dclkio": []}
        dac_ctrl_template = {"spi": [], "reset": []}
        dac_spi_template={"clk": copy(signal_dict_template),
                        "cs_n": copy(signal_dict_template),
                        "sdio": copy(signal_dict_template),
                        "cs_a": copy(signal_dict_template)
                        }

        dac_din = copy(dac_din_template)
        dac_ctrl = copy(dac_ctrl_template)
        for i in range(8):
            dac_din["data"].append(copy(signal_dict_template))
            dac_din["dclkio"].append(copy(signal_dict_template))
        
        dac_ctrl["spi"] = copy(dac_spi_template)
        dac_ctrl["reset"] = copy(signal_dict_template)
        
        dac_din["data"][0]["Pins"]   = "HA06_N HA06_P HA07_N HA02_N HA07_P HA02_P HA03_N HA03_P HA04_N HA04_P HA05_N HA05_P HA00_CC_N HA01_CC_N"
        dac_din["dclkio"][0]["Pins"] = "HA00_CC_P"

        dac_din["data"][1]["Pins"]   = "LA09_P LA09_N LA07_N LA08_N LA07_P LA08_P LA05_N LA04_N LA05_P LA06_N LA04_P LA03_N LA03_P LA06_P"
        dac_din["dclkio"][1]["Pins"] = "LA00_CC_P"

        dac_din["data"][2]["Pins"]   = "HA14_N HA14_P HA12_N HA12_P HA13_N HA10_N HA10_P HA11_N HA11_P HA13_P HA08_N HA08_P HA09_N HA09_P"
        dac_din["dclkio"][2]["Pins"] = "HA01_CC_P"

        dac_din["data"][3]["Pins"]   = "LA14_N LA15_N LA16_N LA15_P LA14_P LA13_N LA16_P LA13_P LA11_N LA12_N LA11_P LA12_P LA10_N LA10_P"
        dac_din["dclkio"][3]["Pins"] = "LA01_CC_P"

        dac_din["data"][4]["Pins"]   = "HA22_N HA19_N HA22_P HA21_N HA21_P HA19_P HA18_N HA20_N HA20_P HA18_P HA15_N HA15_P HA16_N HA16_P"
        dac_din["dclkio"][4]["Pins"] = "HA17_CC_P"

        dac_din["data"][5]["Pins"]   = "LA24_N LA25_N LA24_P LA25_P LA21_N LA21_P LA22_N LA22_P LA23_N LA23_P LA19_N LA19_P LA20_N LA20_P"
        dac_din["dclkio"][5]["Pins"] = "LA17_CC_P"

        dac_din["data"][6]["Pins"]   = "HB08_N HB08_P HB07_N HB07_P HB04_N HB04_P HB01_N HB05_N HB01_P HB05_P HB02_N HB02_P HB03_N HB03_P"
        dac_din["dclkio"][6]["Pins"] = "HB00_CC_P"

        dac_din["data"][7]["Pins"]   = "HB13_N HB12_N HB13_P HB12_P HB15_N HB15_P HB11_N HB09_N HB09_P HB14_N HB14_P HB10_N HB10_P HB11_P"
        dac_din["dclkio"][7]["Pins"] = "HB06_CC_P"

        dac_ctrl["reset"]["Pins"] = "HB16_P"
        dac_ctrl["spi"]["cs_a"]["Pins"] = "LA31_P HB19_P LA30_P"
        dac_ctrl["spi"]["clk"]["Pins"] = "HB16_N"
        dac_ctrl["spi"]["cs_n"]["Pins"] = "LA31_N"
        dac_ctrl["spi"]["sdio"]["Pins"] = "HB06_CC_N"
  
        led = { "led0_g": {"Pins":"HA23_N"},
            "led0_r": {"Pins":"HA23_P"},
            "led1_g": {"Pins":"LA32_P"},
            "led1_r": {"Pins":"HB18_N"}}

        osc = { "osc_sda": {"Pins":"HB20_P"},
                "osc_scl": {"Pins":"HB21_N"},
                "osc_en" : {"Pins":"HB20_N"}}

        mmcx_osc_sel_n = {"mmcx_osc_sel_n": {"Pins":"HB17_CC_N"}}
        
        ref_clk_sel = {"ref_clk_sel": {"Pins":"LA32_N"}}
        
        fmc_clk_m2c2 = {"fmc_clk_m2c2": {"Pins":["LA18_CC_P", "LA18_CC_N"], "diff_term": True, "diff_sig": True}}

        afe = {"ctrl_vadj":[{"channel": 0, 
                            "Pins": "LA02_P LA02_N LA00_CC_N LA01_CC_N LA17_CC_N LA27_P LA27_N LA26_P"}, 
                        {"channel": 1, 
                        "Pins": "LA29_P LA29_N LA28_P LA28_N LA30_N LA33_P HB21_P HB18_P"}],
            "01_01dir":{"Pins": "LA26_N"},
            "01_23dir":{"Pins": "HB00_CC_N"},
            "01_45dir":{"Pins": "HB17_CC_P"},
            "01_67dir":{"Pins": "HA17_CC_N"},
            "01_oen":  {"Pins": "HB19_N"}
        }

        ios += [("shuttler{}_dac_din".format(fmc), i,
            Subsignal("data", Pins(_fmc_pins(fmc, dac_din["data"][i]["Pins"]))),
            Subsignal("dclkio", Pins(_fmc_pins(fmc, dac_din["dclkio"][i]["Pins"]))),
            default_iostandard()
            )for i in range(8)]
        
        # Operate in 3-wire SPI
        ios += [("shuttler{}_dac_ctrl_spi".format(fmc), 0,
            Subsignal("clk", Pins(_fmc_pins(fmc, dac_ctrl["spi"]["clk"]["Pins"]))),
            Subsignal("mosi", Pins(_fmc_pins(fmc, dac_ctrl["spi"]["sdio"]["Pins"]))),
            Subsignal("cs_n", Pins(_fmc_pins(fmc, dac_ctrl["spi"]["cs_n"]["Pins"]))),
            default_iostandard()
            )]

        ios += [("shuttler{}_dac_ctrl".format(fmc), 0,
            Subsignal("reset", Pins(_fmc_pins(fmc, dac_ctrl["reset"]["Pins"]))),
            Subsignal("cs_sel", Pins(_fmc_pins(fmc, dac_ctrl["spi"]["cs_a"]["Pins"]))),
            default_iostandard()
            )]

        # Temporarily change name to get it compile
        ios += [("user_led", 0, Pins(_fmc_pins(fmc, led["led0_g"]["Pins"])), IOStandard("LVCMOS25")),
                ("user_led", 1, Pins(_fmc_pins(fmc, led["led0_r"]["Pins"])), IOStandard("LVCMOS25")),
                ("user_led", 2, Pins(_fmc_pins(fmc, led["led1_g"]["Pins"])), IOStandard("LVCMOS25")),
                ("user_led", 3, Pins(_fmc_pins(fmc, led["led1_r"]["Pins"])), IOStandard("LVCMOS25")),
        ]

        """
        ios += [("shuttler{}_led".format(fmc), 0,
            Subsignal("g", Pins(_fmc_pins(fmc, led["led0_g"]["Pins"]))),
            Subsignal("r", Pins(_fmc_pins(fmc, led["led0_r"]["Pins"]))),
            default_iostandard()
            )]

        ios += [("shuttler{}_led".format(fmc), 1,
            Subsignal("g", Pins(_fmc_pins(fmc, led["led1_g"]["Pins"]))),
            Subsignal("r", Pins(_fmc_pins(fmc, led["led1_r"]["Pins"]))),
            default_iostandard()
            )]
        """
        ios += [("shuttler{}_osc".format(fmc), 0,
            Subsignal("sda", Pins(_fmc_pins(fmc, osc["osc_sda"]["Pins"]))),
            Subsignal("scl", Pins(_fmc_pins(fmc, osc["osc_scl"]["Pins"]))),
            Subsignal("en", Pins(_fmc_pins(fmc, osc["osc_en"]["Pins"]))),
            default_iostandard()
            )]
        
        ios += [("shuttler{}_mmcx_osc_sel_n".format(fmc), 0, 
            Pins(_fmc_pins(fmc, mmcx_osc_sel_n["mmcx_osc_sel_n"]["Pins"])),
            default_iostandard()
            )]

        ios += [("shuttler{}_ref_clk_sel".format(fmc), 0, 
            Pins(_fmc_pins(fmc, ref_clk_sel["ref_clk_sel"]["Pins"])),
            default_iostandard()
            )]

        ios += [("shuttler{}_fmc_clk_m2c2".format(fmc), 0, 
            Subsignal("p", Pins(_fmc_pins(fmc, fmc_clk_m2c2["fmc_clk_m2c2"]["Pins"][0]))),
            Subsignal("n", Pins(_fmc_pins(fmc, fmc_clk_m2c2["fmc_clk_m2c2"]["Pins"][1]))),
            default_iostandard(),
            Misc("DIFF_TERM=TRUE")
            )]
    
        ios += [("shuttler{}_afe_ctrl_vadj".format(fmc), 0,
            Pins(_fmc_pins(fmc,afe["ctrl_vadj"][i]["Pins"])),
            default_iostandard()
            )for i in range(2)]
        
        ios += [("shuttler{}_afe".format(fmc), 0,
            Subsignal("01_01dir", Pins(_fmc_pins(fmc, afe["01_01dir"]["Pins"]))),
            Subsignal("01_23dir", Pins(_fmc_pins(fmc, afe["01_23dir"]["Pins"]))),
            Subsignal("01_45dir", Pins(_fmc_pins(fmc, afe["01_45dir"]["Pins"]))),
            Subsignal("01_67dir", Pins(_fmc_pins(fmc, afe["01_67dir"]["Pins"]))),
            Subsignal("01_oen", Pins(_fmc_pins(fmc, afe["01_oen"]["Pins"]))),
            default_iostandard()
            )]

        return ios