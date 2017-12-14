core_addr = "sayma1.lab.m-labs.hk"

device_db = {
    "core": {
        "type": "local",
        "module": "artiq.coredevice.core",
        "class": "Core",
        "arguments": {"host": core_addr, "ref_period": 1/(150e6)}
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
        "module": "artiq.coredevice.spi",
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
    "ttl_sma0": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 2}
    },
    "ttl_sma1": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 3}
    },

    "sawg0": {
        "type": "local",
        "module": "artiq.coredevice.sawg",
        "class": "SAWG",
        "arguments": {"channel_base": 4, "parallelism": 4}
    },
    "sawg1": {
        "type": "local",
        "module": "artiq.coredevice.sawg",
        "class": "SAWG",
        "arguments": {"channel_base": 14, "parallelism": 4}
    },
    "sawg2": {
        "type": "local",
        "module": "artiq.coredevice.sawg",
        "class": "SAWG",
        "arguments": {"channel_base": 24, "parallelism": 4}
    },
    "sawg3": {
        "type": "local",
        "module": "artiq.coredevice.sawg",
        "class": "SAWG",
        "arguments": {"channel_base": 34, "parallelism": 4}
    },
    "sawg4": {
        "type": "local",
        "module": "artiq.coredevice.sawg",
        "class": "SAWG",
        "arguments": {"channel_base": 44, "parallelism": 4}
    },
    "sawg5": {
        "type": "local",
        "module": "artiq.coredevice.sawg",
        "class": "SAWG",
        "arguments": {"channel_base": 54, "parallelism": 4}
    },
    "sawg6": {
        "type": "local",
        "module": "artiq.coredevice.sawg",
        "class": "SAWG",
        "arguments": {"channel_base": 64, "parallelism": 4}
    },
    "sawg7": {
        "type": "local",
        "module": "artiq.coredevice.sawg",
        "class": "SAWG",
        "arguments": {"channel_base": 74, "parallelism": 4}
    },
}
