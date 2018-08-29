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
for i in range(8):
    device_db["ttl" + str(i)] = {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut" if i < 4 else "TTLOut",
        "arguments": {"channel": i},
    }


# Urukul (EEM1) starting at RTIO channel 8
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


# Sampler (EEM3) starting at RTIO channel 14
device_db["spi_sampler0_adc"] = {
    "type": "local",
    "module": "artiq.coredevice.spi2",
    "class": "SPIMaster",
    "arguments": {"channel": 14}
}
device_db["spi_sampler0_pgia"] = {
    "type": "local",
    "module": "artiq.coredevice.spi2",
    "class": "SPIMaster",
    "arguments": {"channel": 15}
}
device_db["spi_sampler0_cnv"] = {
    "type": "local",
    "module": "artiq.coredevice.ttl",
    "class": "TTLOut",
    "arguments": {"channel": 16},
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


# Zotino (EEM4) starting at RTIO channel 17
device_db["spi_zotino0"] = {
    "type": "local",
    "module": "artiq.coredevice.spi2",
    "class": "SPIMaster",
    "arguments": {"channel": 17}
}
device_db["ttl_zotino0_ldac"] = {
    "type": "local",
    "module": "artiq.coredevice.ttl",
    "class": "TTLOut",
    "arguments": {"channel": 18}
}
device_db["ttl_zotino0_clr"] = {
    "type": "local",
    "module": "artiq.coredevice.ttl",
    "class": "TTLOut",
    "arguments": {"channel": 19}
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


# Grabber (EEM6) starting at RTIO channel 20
device_db["grabber0"] = {
    "type": "local",
    "module": "artiq.coredevice.grabber",
    "class": "Grabber",
    "arguments": {"channel_base": 20}
}


# Urukul (EEM7) starting at RTIO channel 22
device_db.update(
    spi_urukul1={
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "SPIMaster",
        "arguments": {"channel": 22}
    },
    ttl_urukul1_io_update={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 23}
    },
    urukul1_cpld={
        "type": "local",
        "module": "artiq.coredevice.urukul",
        "class": "CPLD",
        "arguments": {
            "spi_device": "spi_urukul1",
            "io_update_device": "ttl_urukul1_io_update",
            "refclk": 100e6,
            "clk_sel": 1
        }
    }
)

for i in range(4):
    device_db["urukul1_ch" + str(i)] = {
        "type": "local",
        "module": "artiq.coredevice.ad9912",
        "class": "AD9912",
        "arguments": {
            "pll_n": 10,
            "chip_select": 4 + i,
            "cpld_device": "urukul1_cpld"
        }
    }


# DIO (EEM8) starting at RTIO channel 24
for i in range(8):
    device_db["ttl" + str(8 + i)] = {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 24 + i},
    }


# DIO (EEM9) starting at RTIO channel 32
for i in range(8):
    device_db["ttl" + str(16 + i)] = {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 32 + i},
    }


# Sampler (EEM10) starting at RTIO channel 40
device_db["spi_sampler1_adc"] = {
    "type": "local",
    "module": "artiq.coredevice.spi2",
    "class": "SPIMaster",
    "arguments": {"channel": 40}
}
device_db["spi_sampler1_pgia"] = {
    "type": "local",
    "module": "artiq.coredevice.spi2",
    "class": "SPIMaster",
    "arguments": {"channel": 41}
}
device_db["spi_sampler1_cnv"] = {
    "type": "local",
    "module": "artiq.coredevice.ttl",
    "class": "TTLOut",
    "arguments": {"channel": 42},
}
device_db["sampler1"] = {
    "type": "local",
    "module": "artiq.coredevice.sampler",
    "class": "Sampler",
    "arguments": {
        "spi_adc_device": "spi_sampler1_adc",
        "spi_pgia_device": "spi_sampler1_pgia",
        "cnv_device": "spi_sampler1_cnv"
    }
}


# Zotino (EEM11) starting at RTIO channel 43
device_db["spi_zotino1"] = {
    "type": "local",
    "module": "artiq.coredevice.spi2",
    "class": "SPIMaster",
    "arguments": {"channel": 43}
}
device_db["ttl_zotino1_ldac"] = {
    "type": "local",
    "module": "artiq.coredevice.ttl",
    "class": "TTLOut",
    "arguments": {"channel": 44}
}
device_db["ttl_zotino1_clr"] = {
    "type": "local",
    "module": "artiq.coredevice.ttl",
    "class": "TTLOut",
    "arguments": {"channel": 45}
}
device_db["zotino1"] = {
    "type": "local",
    "module": "artiq.coredevice.zotino",
    "class": "Zotino",
    "arguments": {
        "spi_device": "spi_zotino1",
        "ldac_device": "ttl_zotino1_ldac",
        "clr_device": "ttl_zotino1_clr"
    }
}


device_db.update(
    led0={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 46}
    },
    led1={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 47}
    },
)

device_db.update(
    ttl_out="ttl4",
    ttl_out_serdes="ttl4",

    loop_out="ttl4",
    loop_in="ttl0",
)
