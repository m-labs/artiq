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

    "ttl_urukul0_io_update": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 16}
    },
    "ttl_urukul1_io_update": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 17}
    },

    "suservo0_ch0": {
        "type": "local",
        "module": "artiq.coredevice.suservo",
        "class": "Channel",
        "arguments": {"channel": 18, "servo_device": "suservo0"}
    },
    "suservo0_ch1": {
        "type": "local",
        "module": "artiq.coredevice.suservo",
        "class": "Channel",
        "arguments": {"channel": 19, "servo_device": "suservo0"}
    },
    "suservo0_ch2": {
        "type": "local",
        "module": "artiq.coredevice.suservo",
        "class": "Channel",
        "arguments": {"channel": 20, "servo_device": "suservo0"}
    },
    "suservo0_ch3": {
        "type": "local",
        "module": "artiq.coredevice.suservo",
        "class": "Channel",
        "arguments": {"channel": 21, "servo_device": "suservo0"}
    },
    "suservo0_ch4": {
        "type": "local",
        "module": "artiq.coredevice.suservo",
        "class": "Channel",
        "arguments": {"channel": 22, "servo_device": "suservo0"}
    },
    "suservo0_ch5": {
        "type": "local",
        "module": "artiq.coredevice.suservo",
        "class": "Channel",
        "arguments": {"channel": 23, "servo_device": "suservo0"}
    },
    "suservo0_ch6": {
        "type": "local",
        "module": "artiq.coredevice.suservo",
        "class": "Channel",
        "arguments": {"channel": 24, "servo_device": "suservo0"}
    },
    "suservo0_ch7": {
        "type": "local",
        "module": "artiq.coredevice.suservo",
        "class": "Channel",
        "arguments": {"channel": 25, "servo_device": "suservo0"}
    },

    "suservo0": {
        "type": "local",
        "module": "artiq.coredevice.suservo",
        "class": "SUServo",
        "arguments": {
            "channel": 26,
            "pgia_device": "spi_sampler0_pgia",
            "cpld_devices": ["urukul0_cpld", "urukul1_cpld"],
            "dds_devices": ["urukul0_dds", "urukul1_dds"],
        }
    },

    "spi_sampler0_pgia": {
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "SPIMaster",
        "arguments": {"channel": 27}
    },

    "spi_urukul0": {
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "SPIMaster",
        "arguments": {"channel": 28}
    },
    "urukul0_cpld": {
        "type": "local",
        "module": "artiq.coredevice.suservo",
        "class": "CPLD",
        "arguments": {
            "spi_device": "spi_urukul0",
            "io_update_device": "ttl_urukul0_io_update",
            "sync_device": "clkgen_dds_sync_in",
            "refclk": 100e6,
            "clk_sel": 0
        }
    },
    "urukul0_dds": {
        "type": "local",
        "module": "artiq.coredevice.suservo",
        "class": "AD9910",
        "arguments": {
            "pll_n": 40,
            "chip_select": 3,
            "cpld_device": "urukul0_cpld",
            "io_update_delay": 0,
            "sync_delay_seed": -1,
        }
    },

    "spi_urukul1": {
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "SPIMaster",
        "arguments": {"channel": 29}
    },
    "urukul1_cpld": {
        "type": "local",
        "module": "artiq.coredevice.suservo",
        "class": "CPLD",
        "arguments": {
            "spi_device": "spi_urukul1",
            "io_update_device": "ttl_urukul1_io_update",
            "sync_device": "clkgen_dds_sync_in",
            "refclk": 100e6,
            "clk_sel": 0
        }
    },
    "urukul1_dds": {
        "type": "local",
        "module": "artiq.coredevice.suservo",
        "class": "AD9910",
        "arguments": {
            "pll_n": 40,
            "chip_select": 3,
            "cpld_device": "urukul1_cpld",
            "io_update_delay": 0,
            "sync_delay_seed": -1,
        }
    },

    "clkgen_dds_sync_in": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLClockGen",
        "arguments": {
            "channel": 30,
            "acc_width": 4
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
