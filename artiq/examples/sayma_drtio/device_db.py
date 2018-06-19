core_addr = "sayma-1.lab.m-labs.hk"

device_db = {
    "core": {
        "type": "local",
        "module": "artiq.coredevice.core",
        "class": "Core",
        "arguments": {"host": core_addr, "ref_period": 1/(8*150e6)}
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
    "rconverter_spi": {
        "type": "local",
        "module": "artiq.coredevice.spi2",
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

for i in range(8):
    device_db["sawg" + str(i)] = {
        "type": "local",
        "module": "artiq.coredevice.sawg",
        "class": "SAWG",
        "arguments": {"channel_base": i*10+6, "parallelism": 4}
    }

for i in range(8):
    device_db["sawg" + str(8+i)] = {
        "type": "local",
        "module": "artiq.coredevice.sawg",
        "class": "SAWG",
        "arguments": {"channel_base": i*10+0x010006, "parallelism": 4}
    }
