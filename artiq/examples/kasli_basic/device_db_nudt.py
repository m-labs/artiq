core_addr = "kasli-1.lab.m-labs.hk"

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


# DIO (EEM5) starting at RTIO channel 0
# DIO (EEM6) starting at RTIO channel 8
for i in range(16):
    device_db["ttl" + str(i)] = {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut" if i < 4 else "TTLOut",
        "arguments": {"channel": i},
    }


# Urukul (EEM1) starting at RTIO channel 16
device_db.update(
    spi_urukul0={
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "SPIMaster",
        "arguments": {"channel": 16}
    },
    ttl_urukul0_io_update={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 17}
    },
    ttl_urukul0_sw0={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 18}
    },
    ttl_urukul0_sw1={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 19}
    },
    ttl_urukul0_sw2={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 20}
    },
    ttl_urukul0_sw3={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 21}
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


# Sampler (EEM3) starting at RTIO channel 22
device_db["spi_sampler0_adc"] = {
    "type": "local",
    "module": "artiq.coredevice.spi2",
    "class": "SPIMaster",
    "arguments": {"channel": 22}
}
device_db["spi_sampler0_pgia"] = {
    "type": "local",
    "module": "artiq.coredevice.spi2",
    "class": "SPIMaster",
    "arguments": {"channel": 23}
}
device_db["spi_sampler0_cnv"] = {
    "type": "local",
    "module": "artiq.coredevice.ttl",
    "class": "TTLOut",
    "arguments": {"channel": 24},
}
device_db["sampler0"] = {
    "type": "local",
    "module": "artiq.coredevice.sampler",
    "class": "Sampler",
    "arguments": {
        "spi_adc_device": "spi_sampler0_adc",
        "spi_pgia_device": "spi_sampler0_pgia",
        "cnv_device": "spi_sampler0_cnv"
    }
}


# Zotino (EEM4) starting at RTIO channel 25
device_db["spi_zotino0"] = {
    "type": "local",
    "module": "artiq.coredevice.spi2",
    "class": "SPIMaster",
    "arguments": {"channel": 25}
}
device_db["ttl_zotino0_ldac"] = {
    "type": "local",
    "module": "artiq.coredevice.ttl",
    "class": "TTLOut",
    "arguments": {"channel": 26}
}
device_db["ttl_zotino0_clr"] = {
    "type": "local",
    "module": "artiq.coredevice.ttl",
    "class": "TTLOut",
    "arguments": {"channel": 27}
}
device_db["zotino0"] = {
    "type": "local",
    "module": "artiq.coredevice.zotino",
    "class": "Zotino",
    "arguments": {
        "spi_device": "spi_zotino0",
        "ldac_device": "ttl_zotino0_ldac",
        "clr_device": "ttl_zotino0_clr"
    }
}

device_db.update(
    led0={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 28}
    },
    led1={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 29}
    },
)
