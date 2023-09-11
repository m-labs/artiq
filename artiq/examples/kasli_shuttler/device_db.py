core_addr = "192.168.1.73"

device_db = {
    "core": {
        "type": "local",
        "module": "artiq.coredevice.core",
        "class": "Core",
        "arguments": {"host": core_addr, "ref_period": 1e-09, "target": "rv32g"},
    },
    "core_log": {
        "type": "controller",
        "host": "::1",
        "port": 1068,
        "command": "aqctl_corelog -p {port} --bind {bind} " + core_addr
    },
    "core_moninj": {
        "type": "controller",
        "host": "::1",
        "port_proxy": 1383,
        "port": 1384,
        "command": "aqctl_moninj_proxy --port-proxy {port_proxy} --port-control {port} --bind {bind} " + core_addr
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
        "class": "I2CSwitch",
        "arguments": {"address": 0xe0}
    },
    "i2c_switch1": {
        "type": "local",
        "module": "artiq.coredevice.i2c",
        "class": "I2CSwitch",
        "arguments": {"address": 0xe2}
    },
}

device_db["efc_led0"] = {
    "type": "local",
    "module": "artiq.coredevice.ttl",
    "class": "TTLOut",
    "arguments": {"channel": 0x040000},
}

device_db["efc_led1"] = {
    "type": "local",
    "module": "artiq.coredevice.ttl",
    "class": "TTLOut",
    "arguments": {"channel": 0x040001},
}

device_db["pdq_config"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Config",
    "arguments": {"channel": 0x040002},
}

device_db["pdq_trigger"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Trigger",
    "arguments": {"channel": 0x040003},
}

device_db["pdq0_volt"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Volt",
    "arguments": {"channel": 0x040004},
}

device_db["pdq0_dds"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Dds",
    "arguments": {"channel": 0x040005},
}

device_db["pdq1_volt"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Volt",
    "arguments": {"channel": 0x040006},
}

device_db["pdq1_dds"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Dds",
    "arguments": {"channel": 0x040007},
}

device_db["pdq2_volt"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Volt",
    "arguments": {"channel": 0x040008},
}

device_db["pdq2_dds"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Dds",
    "arguments": {"channel": 0x040009},
}

device_db["pdq3_volt"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Volt",
    "arguments": {"channel": 0x04000A},
}

device_db["pdq3_dds"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Dds",
    "arguments": {"channel": 0x04000B},
}

device_db["pdq4_volt"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Volt",
    "arguments": {"channel": 0x04000C},
}

device_db["pdq4_dds"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Dds",
    "arguments": {"channel": 0x04000D},
}

device_db["pdq5_volt"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Volt",
    "arguments": {"channel": 0x04000E},
}

device_db["pdq5_dds"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Dds",
    "arguments": {"channel": 0x04000F},
}

device_db["pdq6_volt"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Volt",
    "arguments": {"channel": 0x040010},
}

device_db["pdq6_dds"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Dds",
    "arguments": {"channel": 0x040011},
}

device_db["pdq7_volt"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Volt",
    "arguments": {"channel": 0x040012},
}

device_db["pdq7_dds"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Dds",
    "arguments": {"channel": 0x040013},
}

device_db["pdq8_volt"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Volt",
    "arguments": {"channel": 0x040014},
}

device_db["pdq8_dds"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Dds",
    "arguments": {"channel": 0x040015},
}

device_db["pdq9_volt"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Volt",
    "arguments": {"channel": 0x040016},
}

device_db["pdq9_dds"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Dds",
    "arguments": {"channel": 0x040017},
}

device_db["pdq10_volt"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Volt",
    "arguments": {"channel": 0x040018},
}

device_db["pdq10_dds"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Dds",
    "arguments": {"channel": 0x040019},
}

device_db["pdq11_volt"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Volt",
    "arguments": {"channel": 0x04001A},
}

device_db["pdq11_dds"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Dds",
    "arguments": {"channel": 0x04001B},
}

device_db["pdq12_volt"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Volt",
    "arguments": {"channel": 0x04001C},
}

device_db["pdq12_dds"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Dds",
    "arguments": {"channel": 0x04001D},
}

device_db["pdq13_volt"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Volt",
    "arguments": {"channel": 0x04001E},
}

device_db["pdq13_dds"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Dds",
    "arguments": {"channel": 0x04001F},
}

device_db["pdq14_volt"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Volt",
    "arguments": {"channel": 0x040020},
}

device_db["pdq14_dds"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Dds",
    "arguments": {"channel": 0x040021},
}

device_db["pdq15_volt"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Volt",
    "arguments": {"channel": 0x040022},
}

device_db["pdq15_dds"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Dds",
    "arguments": {"channel": 0x040023},
}

device_db["spi_afe_relay"] = {
    "type": "local",
    "module": "artiq.coredevice.spi2",
    "class": "SPIMaster",
    "arguments": {"channel": 0x040024}
}

device_db["afe_relay"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "Relay",
    "arguments": {
        "spi_device": "spi_afe_relay",
    }
}

device_db["spi_afe_adc"] = {
    "type": "local",
    "module": "artiq.coredevice.spi2",
    "class": "SPIMaster",
    "arguments": {"channel": 0x040025}
}

device_db["afe_adc"] = {
    "type": "local",
    "module": "artiq.coredevice.shuttler",
    "class": "ADC",
    "arguments": {
        "spi_device": "spi_afe_adc",
    }
}
