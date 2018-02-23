core_addr = "sayma-1.lab.m-labs.hk"

device_db = {
    "core": {
        "type": "local",
        "module": "artiq.coredevice.core",
        "class": "Core",
        "arguments": {"host": core_addr, "ref_period": 1/150e6, "ref_multiplier": 1}
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

    "converter_spi": {
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "NRTSPIMaster",
    },
    "ad9154_spi0": {
        "type": "local",
        "module": "artiq.coredevice.ad9154_spi",
        "class": "AD9154",
        "arguments": {"spi_device": "converter_spi", "chip_select": 2}
    },
    "ad9154_spi1": {
        "type": "local",
        "module": "artiq.coredevice.ad9154_spi",
        "class": "AD9154",
        "arguments": {"spi_device": "converter_spi", "chip_select": 3}
    },

    "led0": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 0}
    },
    "led1": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 1}
    },
    "led1": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 2}
    },
    "led1": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 3}
    },
    "ttl_sma_out": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 4}
    },
    "ttl_sma_in": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 5}
    },

    "sawg0": {
        "type": "local",
        "module": "artiq.coredevice.sawg",
        "class": "SAWG",
        "arguments": {"channel_base": 6, "parallelism": 4}
    },
    "sawg1": {
        "type": "local",
        "module": "artiq.coredevice.sawg",
        "class": "SAWG",
        "arguments": {"channel_base": 16, "parallelism": 4}
    },
    "sawg2": {
        "type": "local",
        "module": "artiq.coredevice.sawg",
        "class": "SAWG",
        "arguments": {"channel_base": 26, "parallelism": 4}
    },
    "sawg3": {
        "type": "local",
        "module": "artiq.coredevice.sawg",
        "class": "SAWG",
        "arguments": {"channel_base": 36, "parallelism": 4}
    },
    "sawg4": {
        "type": "local",
        "module": "artiq.coredevice.sawg",
        "class": "SAWG",
        "arguments": {"channel_base": 46, "parallelism": 4}
    },
    "sawg5": {
        "type": "local",
        "module": "artiq.coredevice.sawg",
        "class": "SAWG",
        "arguments": {"channel_base": 56, "parallelism": 4}
    },
    "sawg6": {
        "type": "local",
        "module": "artiq.coredevice.sawg",
        "class": "SAWG",
        "arguments": {"channel_base": 66, "parallelism": 4}
    },
    "sawg7": {
        "type": "local",
        "module": "artiq.coredevice.sawg",
        "class": "SAWG",
        "arguments": {"channel_base": 76, "parallelism": 4}
    },
}
