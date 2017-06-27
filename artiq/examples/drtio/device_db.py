core_addr = "kc705.lab.m-labs.hk"

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
    "led4": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 4},
    },
    "led5": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 5},
    },
    "led6": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 6},
    },
    "led7": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 7},
    },

    "smap": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut",
        "arguments": {"channel": 8}
    },
    "sman": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut",
        "arguments": {"channel": 9}
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
    "rled4": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 0x010004},
    },
    "rled5": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 0x010005},
    },
    "rled6": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 0x010006},
    },
    "rled7": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 0x010007},
    },

    "rsmap": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut",
        "arguments": {"channel": 0x010008}
    },
    "rsman": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut",
        "arguments": {"channel": 0x010009}
    },

    "converter_spi": {
        "type": "local",
        "module": "artiq.coredevice.spi",
        "class": "NRTSPIMaster",
    },
    "ad9154_spi": {
        "type": "local",
        "module": "artiq.coredevice.ad9154_spi",
        "class": "AD9154",
        "arguments": {"spi_device": "converter_spi", "chip_select": 1}
    },
    "rconverter_spi": {
        "type": "local",
        "module": "artiq.coredevice.spi",
        "class": "NRTSPIMaster",
        "arguments": {"busno": 0x010000}
    },
    "rad9154_spi": {
        "type": "local",
        "module": "artiq.coredevice.ad9154_spi",
        "class": "AD9154",
        "arguments": {"spi_device": "rconverter_spi", "chip_select": 1}
    },
}
