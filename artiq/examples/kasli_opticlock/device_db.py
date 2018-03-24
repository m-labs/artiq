# This is an example device database that needs to be adapted to your setup.
# The list of devices here is not exhaustive.

core_addr = "vettel.ber.quartiq.de"

device_db = {
    "core": {
        "type": "local",
        "module": "artiq.coredevice.core",
        "class": "Core",
        "arguments": {"host": core_addr, "ref_period": 1e-9}
    },
    "core_log": {
        "type": "controller",
        "host": "::1",
        "port": 1068,
        "command": "aqctl_corelog -p {port} --bind {bind} " + core_addr
    },
    "core_cache": {
        "type": "local",
        "module": "artiq.coredevice.cache",
        "class": "CoreCache"
    },
    "core_dma": {
        "type": "local",
        "module": "artiq.coredevice.dma",
        "class": "CoreDMA"
    },

    "i2c_switch0": {
        "type": "local",
        "module": "artiq.coredevice.i2c",
        "class": "PCA9548",
        "arguments": {"address": 0xe0}
    },
    "i2c_switch1": {
        "type": "local",
        "module": "artiq.coredevice.i2c",
        "class": "PCA9548",
        "arguments": {"address": 0xe2}
    },

    "ttl0": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut",
        "arguments": {"channel": 0},
    },
    "ttl1": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut",
        "arguments": {"channel": 1},
    },
    "ttl2": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut",
        "arguments": {"channel": 2},
    },
    "ttl3": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut",
        "arguments": {"channel": 3},
    },

    "ttl4": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 4},
    },
    "ttl5": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 5},
    },
    "ttl6": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 6},
    },
    "ttl7": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 7},
    },
    "ttl8": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 8},
    },
    "ttl9": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 9},
    },
    "ttl10": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 10},
    },
    "ttl11": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 11},
    },
    "ttl12": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 12},
    },
    "ttl13": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 13},
    },
    "ttl14": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 14},
    },
    "ttl15": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 15},
    },
    "ttl16": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 16},
    },
    "ttl17": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 17},
    },
    "ttl18": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 18},
    },
    "ttl19": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 19},
    },
    "ttl20": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 20},
    },
    "ttl21": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 21},
    },
    "ttl22": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 22},
    },
    "ttl23": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 23},
    },

    "spi_novogorny0": {
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "SPIMaster",
        "arguments": {"channel": 24}
    },
    "ttl_novogorny0_cnv": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 25}
    },
    "novogorny0" : {
        "type": "local",
        "module": "artiq.coredevice.novogorny",
        "class": "Novogorny",
        "arguments": {
            "spi_device": "spi_novogorny0",
            "cnv_device": "ttl_novogorny0_cnv",
        }
    },

    "spi_urukul0": {
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "SPIMaster",
        "arguments": {"channel": 26}
    },
    "ttl_urukul0_io_update": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 27}
    },
    "ttl_urukul0_sw0": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 28}
    },
    "ttl_urukul0_sw1": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 29}
    },
    "ttl_urukul0_sw2": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 30}
    },
    "ttl_urukul0_sw3": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 31}
    },
    "urukul0_cpld": {
        "type": "local",
        "module": "artiq.coredevice.urukul",
        "class": "CPLD",
        "arguments": {
            "spi_device": "spi_urukul0",
            "io_update_device": "ttl_urukul0_io_update",
            "refclk": 100e6,
            "clk_sel": 1
        }
    },
    "urukul0_ch0": {
        "type": "local",
        "module": "artiq.coredevice.ad9912",
        "class": "AD9912",
        "arguments": {
            "pll_n": 10,
            "chip_select": 4,
            "cpld_device": "urukul0_cpld",
            "sw_device": "ttl_urukul0_sw0"
        }
    },
    "urukul0_ch1": {
        "type": "local",
        "module": "artiq.coredevice.ad9912",
        "class": "AD9912",
        "arguments": {
            "pll_n": 10,
            "chip_select": 5,
            "cpld_device": "urukul0_cpld",
            "sw_device": "ttl_urukul0_sw1"
        }
    },
    "urukul0_ch2": {
        "type": "local",
        "module": "artiq.coredevice.ad9912",
        "class": "AD9912",
        "arguments": {
            "pll_n": 10,
            "chip_select": 6,
            "cpld_device": "urukul0_cpld",
            "sw_device": "ttl_urukul0_sw2"
        }
    },
    "urukul0_ch3": {
        "type": "local",
        "module": "artiq.coredevice.ad9912",
        "class": "AD9912",
        "arguments": {
            "pll_n": 10,
            "chip_select": 7,
            "cpld_device": "urukul0_cpld",
            "sw_device": "ttl_urukul0_sw3"
        }
    },

    "led0": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 32}
    },
    "led1": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 33}
    },

    "spi_zotino0": {
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "SPIMaster",
        "arguments": {"channel": 36}
    },
    "ttl_zotino0_ldac": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 37}
    },
    "ttl_zotino0_clr": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 38}
    },
    "zotino0": {
        "type": "local",
        "module": "artiq.coredevice.zotino",
        "class": "Zotino",
        "arguments": {
            "spi_device": "spi_zotino0",
            "ldac_device": "ttl_zotino0_ldac",
            "clr_device": "ttl_zotino0_clr"
        }
    }
}
