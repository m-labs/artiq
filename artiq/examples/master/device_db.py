# Copy of the KC705 device database, for compatibility of the buildbot and
# unit tests with release-3.
# Remove and update buildbot when release-3 is no longer maintained.

core_addr = "kc705-1.lab.m-labs.hk"

device_db = {
    # Core device
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
    "core_dds": {
        "type": "local",
        "module": "artiq.coredevice.dds",
        "class": "DDSGroupAD9914",
        "arguments": {
            "sysclk": 3e9,
            "first_dds_bus_channel": 39,
            "dds_bus_count": 2,
            "dds_channel_count": 3
        }
    },

    "i2c_switch": {
        "type": "local",
        "module": "artiq.coredevice.i2c",
        "class": "PCA9548"
    },

    # Generic TTL
    "ttl0": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 0},
        "comment": "This is a fairly long comment, shown as tooltip."
    },
    "ttl1": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 1},
        "comment": "Hello World"
    },
    "ttl2": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 2}
    },
    "ttl3": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut",
        "arguments": {"channel": 3}
    },

    "ttl4": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 4}
    },
    "ttl5": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 5}
    },
    "ttl6": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 6}
    },
    "ttl7": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut",
        "arguments": {"channel": 7}
    },
    "ttl_sma": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut",
        "arguments": {"channel": 18}
    },
    "led": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 19}
    },
    "ttl_clock_la32_p": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLClockGen",
        "arguments": {"channel": 21}
    },

    # Generic SPI
    "spi0": {
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "SPIMaster",
        "arguments": {"channel": 23}
    },
    "spi_mmc": {
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "SPIMaster",
        "arguments": {"channel": 26}
    },

    # FMC DIO used to connect to Zotino
    "fmcdio_dirctl_clk": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 27}
    },
    "fmcdio_dirctl_ser": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 28}
    },
    "fmcdio_dirctl_latch": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 29}
    },
    "fmcdio_dirctl": {
        "type": "local",
        "module": "artiq.coredevice.shiftreg",
        "class": "ShiftReg",
        "arguments": {"clk": "fmcdio_dirctl_clk",
                      "ser": "fmcdio_dirctl_ser",
                      "latch": "fmcdio_dirctl_latch"}
    },

    # DAC
    "spi_ams101": {
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "SPIMaster",
        "arguments": {"channel": 22}
    },
    "ttl_ams101_ldac": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 20}
    },
    "spi_zotino": {
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "SPIMaster",
        "arguments": {"channel": 30}
    },
    "ttl_zotino_ldac": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 31}
    },
    "dac_zotino": {
        "type": "local",
        "module": "artiq.coredevice.ad5360",
        "class": "AD5360",
        "arguments": {
            "spi_device": "spi_zotino",
            "ldac_device": "ttl_zotino_ldac",
            "div_write": 30,
            "div_read": 40
        }
    },

    "spi_urukul": {
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "SPIMaster",
        "arguments": {"channel": 32}
    },
    "ttl_urukul_io_update": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 33}
    },
    "ttl_urukul_sw0": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 35}
    },
    "ttl_urukul_sw1": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 36}
    },
    "ttl_urukul_sw2": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 37}
    },
    "ttl_urukul_sw3": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 38}
    },
    "urukul_cpld": {
        "type": "local",
        "module": "artiq.coredevice.urukul",
        "class": "CPLD",
        "arguments": {
            "spi_device": "spi_urukul",
            "io_update_device": "ttl_urukul_io_update",
            "refclk": 100e6
        }
    },
    "urukul_ch0a": {
        "type": "local",
        "module": "artiq.coredevice.ad9912",
        "class": "AD9912",
        "arguments": {
            "pll_n": 10,
            "chip_select": 4,
            "cpld_device": "urukul_cpld",
            "sw_device": "ttl_urukul_sw0"
        }
    },
    "urukul_ch1a": {
        "type": "local",
        "module": "artiq.coredevice.ad9912",
        "class": "AD9912",
        "arguments": {
            "pll_n": 10,
            "chip_select": 5,
            "cpld_device": "urukul_cpld",
            "sw_device": "ttl_urukul_sw1"
        }
    },
    "urukul_ch2a": {
        "type": "local",
        "module": "artiq.coredevice.ad9912",
        "class": "AD9912",
        "arguments": {
            "pll_n": 10,
            "chip_select": 6,
            "cpld_device": "urukul_cpld",
            "sw_device": "ttl_urukul_sw2"
        }
    },
    "urukul_ch3a": {
        "type": "local",
        "module": "artiq.coredevice.ad9912",
        "class": "AD9912",
        "arguments": {
            "pll_n": 10,
            "chip_select": 7,
            "cpld_device": "urukul_cpld",
            "sw_device": "ttl_urukul_sw3"
        }
    },
    "urukul_ch0b": {
        "type": "local",
        "module": "artiq.coredevice.ad9910",
        "class": "AD9910",
        "arguments": {
            "pll_n": 40,
            "chip_select": 4,
            "cpld_device": "urukul_cpld",
            "sw_device": "ttl_urukul_sw0"
        }
    },
    "urukul_ch1b": {
        "type": "local",
        "module": "artiq.coredevice.ad9910",
        "class": "AD9910",
        "arguments": {
            "pll_n": 40,
            "chip_select": 5,
            "cpld_device": "urukul_cpld",
            "sw_device": "ttl_urukul_sw1"
        }
    },
    "urukul_ch2b": {
        "type": "local",
        "module": "artiq.coredevice.ad9910",
        "class": "AD9910",
        "arguments": {
            "pll_n": 40,
            "chip_select": 6,
            "cpld_device": "urukul_cpld",
            "sw_device": "ttl_urukul_sw2"
        }
    },
    "urukul_ch3b": {
        "type": "local",
        "module": "artiq.coredevice.ad9910",
        "class": "AD9910",
        "arguments": {
            "pll_n": 40,
            "chip_select": 7,
            "cpld_device": "urukul_cpld",
            "sw_device": "ttl_urukul_sw3"
        }
    },

    # AD9914 DDS
    "dds0": {
        "type": "local",
        "module": "artiq.coredevice.dds",
        "class": "DDSChannelAD9914",
        "arguments": {"bus_channel": 39, "channel": 0},
        "comment": "Comments work in DDS panel as well"
    },
    "dds1": {
        "type": "local",
        "module": "artiq.coredevice.dds",
        "class": "DDSChannelAD9914",
        "arguments": {"bus_channel": 39, "channel": 1}
    },
    "dds2": {
        "type": "local",
        "module": "artiq.coredevice.dds",
        "class": "DDSChannelAD9914",
        "arguments": {"bus_channel": 39, "channel": 2}
    },

    # Aliases
    "ttl_out": "ttl0",
    "ttl_out_serdes": "ttl0",

    "loop_out": "ttl0",
    "loop_in": "ttl3",
    "loop_clock_out": "ttl_clock_la32_p",
    "loop_clock_in": "ttl7",

    "pmt": "ttl3",
    "bd_dds": "dds0",
    "bd_sw": "ttl0",
    "bdd_dds": "dds1",
    "bdd_sw": "ttl1"
}
