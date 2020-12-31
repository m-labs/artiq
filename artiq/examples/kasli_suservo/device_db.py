core_addr = "10.0.16.121"

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

    "suservo0_ch0": {
        "type": "local",
        "module": "artiq.coredevice.suservo",
        "class": "Channel",
        "arguments": {"channel": 16, "servo_device": "suservo0"}
    },
    "suservo0_ch1": {
        "type": "local",
        "module": "artiq.coredevice.suservo",
        "class": "Channel",
        "arguments": {"channel": 17, "servo_device": "suservo0"}
    },
    "suservo0_ch2": {
        "type": "local",
        "module": "artiq.coredevice.suservo",
        "class": "Channel",
        "arguments": {"channel": 18, "servo_device": "suservo0"}
    },
    "suservo0_ch3": {
        "type": "local",
        "module": "artiq.coredevice.suservo",
        "class": "Channel",
        "arguments": {"channel": 19, "servo_device": "suservo0"}
    },
    "suservo0_ch4": {
        "type": "local",
        "module": "artiq.coredevice.suservo",
        "class": "Channel",
        "arguments": {"channel": 20, "servo_device": "suservo0"}
    },
    "suservo0_ch5": {
        "type": "local",
        "module": "artiq.coredevice.suservo",
        "class": "Channel",
        "arguments": {"channel": 21, "servo_device": "suservo0"}
    },
    "suservo0_ch6": {
        "type": "local",
        "module": "artiq.coredevice.suservo",
        "class": "Channel",
        "arguments": {"channel": 22, "servo_device": "suservo0"}
    },
    "suservo0_ch7": {
        "type": "local",
        "module": "artiq.coredevice.suservo",
        "class": "Channel",
        "arguments": {"channel": 23, "servo_device": "suservo0"}
    },

    "suservo0": {
        "type": "local",
        "module": "artiq.coredevice.suservo",
        "class": "SUServo",
        "arguments": {
            "channel": 24,
            "pgia_device": "spi_sampler0_pgia",
            "cpld0_device": "urukul0_cpld",
            "cpld1_device": "urukul1_cpld",
            "dds0_device": "urukul0_dds",
            "dds1_device": "urukul1_dds"
        }
    },

    "spi_sampler0_pgia": {
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "SPIMaster",
        "arguments": {"channel": 25}
    },

    "spi_urukul0": {
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "SPIMaster",
        "arguments": {"channel": 26}
    },
    "urukul0_cpld": {
        "type": "local",
        "module": "artiq.coredevice.urukul",
        "class": "CPLD",
        "arguments": {
            "spi_device": "spi_urukul0",
            "refclk": 100e6,
            "clk_sel": 0
        }
    },
    "urukul0_dds": {
        "type": "local",
        "module": "artiq.coredevice.ad9910",
        "class": "AD9910",
        "arguments": {
            "pll_n": 40,
            "chip_select": 3,
            "cpld_device": "urukul0_cpld",
        }
    },

    "spi_urukul1": {
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "SPIMaster",
        "arguments": {"channel": 27}
    },
    "urukul1_cpld": {
        "type": "local",
        "module": "artiq.coredevice.urukul",
        "class": "CPLD",
        "arguments": {
            "spi_device": "spi_urukul1",
            "refclk": 100e6,
            "clk_sel": 0
        }
    },
    "urukul1_dds": {
        "type": "local",
        "module": "artiq.coredevice.ad9910",
        "class": "AD9910",
        "arguments": {
            "pll_n": 40,
            "chip_select": 3,
            "cpld_device": "urukul1_cpld",
        }
    },

    "led0": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 28}
    },
    "led1": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 29}
    }
}
