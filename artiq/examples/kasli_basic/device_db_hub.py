core_addr = "staging.ber.quartiq.de"

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


device_db.update({
    "ttl" + str(i): {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut" if i < 4 else "TTLOut",
        "arguments": {"channel": i},
    } for i in range(24)
})


device_db.update({
    "spi_sampler0_adc": {
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "SPIMaster",
        "arguments": {"channel": 24}
    },
    "spi_sampler0_pgia": {
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "SPIMaster",
        "arguments": {"channel": 25}
    },
    "spi_sampler0_cnv": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 26},
    },
    "sampler0": {
        "type": "local",
        "module": "artiq.coredevice.sampler",
        "class": "Sampler",
        "arguments": {
            "spi_adc_device": "spi_sampler0_adc",
            "spi_pgia_device": "spi_sampler0_pgia",
            "cnv_device": "spi_sampler0_cnv"
        }
    }
})

for j in range(3):
    device_db.update({
        "spi_urukul{}".format(j): {
            "type": "local",
            "module": "artiq.coredevice.spi2",
            "class": "SPIMaster",
            "arguments": {"channel": 27 + 2*j}
        },
        "ttl_urukul{}_io_update".format(j): {
            "type": "local",
            "module": "artiq.coredevice.ttl",
            "class": "TTLOut",
            "arguments": {"channel": 28 + 2*j}
        },
        "urukul{}_cpld".format(j): {
            "type": "local",
            "module": "artiq.coredevice.urukul",
            "class": "CPLD",
            "arguments": {
                "spi_device": "spi_urukul{}".format(j),
                "io_update_device": "ttl_urukul{}_io_update".format(j),
                "refclk": 100e6,
                "clk_sel": 0
            }
        }
    })

    device_db.update({
        "urukul{}_ch{}".format(j, i): {
            "type": "local",
            "module": "artiq.coredevice.ad9910",
            "class": "AD9910",
            "arguments": {
                "pll_n": 40,
                "chip_select": 4 + i,
                "cpld_device": "urukul{}_cpld".format(j)
            }
        } for i in range(4)
    })


device_db.update({
    "led0": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 33}
    },
    "led1": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 34}
    }
})


device_db.update({
    "spi_zotino0": {
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "SPIMaster",
        "arguments": {"channel": 35}
    },
    "ttl_zotino0_ldac": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 36}
    },
    "ttl_zotino0_clr": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 37}
    },
    "zotino0": {
        "type": "local",
        "module": "artiq.coredevice.zotino",
        "class": "Zotino",
        "arguments": {
            "spi_device": "spi_zotino0",
            "ldac_device": "ttl_zotino0_ldac",
            "clr_device": "ttl_zotino0_clr"
        }
    }
})
