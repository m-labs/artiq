core_addr = "kasli-2.lab.m-labs.hk"

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
}

for i in range(8):
    device_db["ttl" + str(i)] = {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut",
        "arguments": {"channel": i},
    }

device_db.update(
    spi_urukul0={
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "SPIMaster",
        "arguments": {"channel": 8}
    },
    ttl_urukul0_io_update={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 9}
    },
    ttl_urukul0_sw0={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 10}
    },
    ttl_urukul0_sw1={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 11}
    },
    ttl_urukul0_sw2={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 12}
    },
    ttl_urukul0_sw3={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 13}
    },
    urukul0_cpld={
        "type": "local",
        "module": "artiq.coredevice.urukul",
        "class": "CPLD",
        "arguments": {
            "spi_device": "spi_urukul0",
            "io_update_device": "ttl_urukul0_io_update",
            "refclk": 125e6,
            "clk_sel": 0
        }
    }
)

for i in range(4):
    device_db["urukul0_ch" + str(i)] = {
        "type": "local",
        "module": "artiq.coredevice.ad9910",
        "class": "AD9910",
        "arguments": {
            "pll_n": 32,
            "chip_select": 4 + i,
            "cpld_device": "urukul0_cpld",
            "sw_device": "ttl_urukul0_sw" + str(i)
        }
    }

for i in range(2):
    device_db["spi_zotino{}".format(i)] = {
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "SPIMaster",
        "arguments": {"channel": 14+3*i+0}
    }
    device_db["ttl_zotino{}_ldac".format(i)] = {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 14+3*i+1}
    }
    device_db["ttl_zotino{}_clr".format(i)] = {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 14+3*i+2}
    }
    device_db["zotino{}".format(i)] = {
        "type": "local",
        "module": "artiq.coredevice.zotino",
        "class": "Zotino",
        "arguments": {
            "spi_device": "spi_zotino{}".format(i),
            "ldac_device": "ttl_zotino{}_ldac".format(i),
            "clr_device": "ttl_zotino{}_clr".format(i)
        }
    }

device_db.update(
    led0={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 22}
    },
    led1={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 23}
    },
)
