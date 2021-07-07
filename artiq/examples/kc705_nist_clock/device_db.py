# This is an example device database that needs to be adapted to your setup.
# The list of devices here is not exhaustive.

core_addr = "192.168.1.50"

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

    # AD9914 DDS
    "ad9914dds0": {
        "type": "local",
        "module": "artiq.coredevice.ad9914",
        "class": "AD9914",
        "arguments": {"sysclk": 3e9, "bus_channel": 27, "channel": 0},
        "comment": "Comments work in DDS panel as well"
    },
    "ad9914dds1": {
        "type": "local",
        "module": "artiq.coredevice.ad9914",
        "class": "AD9914",
        "arguments": {"sysclk": 3e9, "bus_channel": 27, "channel": 1}
    },
    "ad9914dds2": {
        "type": "local",
        "module": "artiq.coredevice.ad9914",
        "class": "AD9914",
        "arguments": {"sysclk": 3e9, "bus_channel": 27, "channel": 2}
    },

    # Aliases
    "ttl_out": "ttl0",
    "ttl_out_serdes": "ttl0",

    "loop_out": "ttl0",
    "loop_in": "ttl3",
    "loop_clock_out": "ttl_clock_la32_p",
    "loop_clock_in": "ttl7",

    "pmt": "ttl3",
    "bd_dds": "ad9914dds0",
    "bd_sw": "ttl0",
    "bdd_dds": "ad9914dds1",
    "bdd_sw": "ttl1"
}
