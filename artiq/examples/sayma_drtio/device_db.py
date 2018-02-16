core_addr = "sayma1.lab.m-labs.hk"

device_db = {
    "core": {
        "type": "local",
        "module": "artiq.coredevice.core",
        "class": "Core",
        "arguments": {"host": core_addr, "ref_period": 2e-9}
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

    "led0": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 0},
    },
    "led1": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 1},
    },
    "led2": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 2},
    },
    "led3": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 3},
    },
    "ttl_sma_out": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut",
        "arguments": {"channel": 4}
    },
    "ttl_sma_in": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut",
        "arguments": {"channel": 5}
    },

    "rled0": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 0x010000},
    },
    "rled1": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 0x010001},
    },
    "rled2": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 0x010002},
    },
    "rled3": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 0x010003},
    },
    "rttl_sma_out": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut",
        "arguments": {"channel": 0x010004}
    },
    "rttl_sma_in": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut",
        "arguments": {"channel": 0x010005}
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
    "rconverter_spi": {
        "type": "local",
        "module": "artiq.coredevice.spi",
        "class": "NRTSPIMaster",
        "arguments": {"busno": 0x010000}
    },
    "rad9154_spi0": {
        "type": "local",
        "module": "artiq.coredevice.ad9154_spi",
        "class": "AD9154",
        "arguments": {"spi_device": "rconverter_spi", "chip_select": 2}
    },
    "rad9154_spi1": {
        "type": "local",
        "module": "artiq.coredevice.ad9154_spi",
        "class": "AD9154",
        "arguments": {"spi_device": "rconverter_spi", "chip_select": 3}
    },
}
