core_addr = "192.168.1.60"

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
}

for i in range(4):
    device_db["led" + str(i)] = {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": i},
    }


for i in range(2):
    device_db["ttl" + str(i)] = {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut",
        "arguments": {"channel": 4 + i},
    }


device_db.update(
    fmcdio_dirctl_clk={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 6}
    },
    fmcdio_dirctl_ser={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 7}
    },
    fmcdio_dirctl_latch={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 8}
    },
    fmcdio_dirctl={
        "type": "local",
        "module": "artiq.coredevice.shiftreg",
        "class": "ShiftReg",
        "arguments": {"clk": "fmcdio_dirctl_clk",
                      "ser": "fmcdio_dirctl_ser",
                      "latch": "fmcdio_dirctl_latch"}
    }
)

device_db.update(
    spi_urukul0={
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "SPIMaster",
        "arguments": {"channel": 17}
    },
    ttl_urukul0_io_update={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 18}
    },
    ttl_urukul0_sw0={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 19}
    },
    ttl_urukul0_sw1={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 20}
    },
    ttl_urukul0_sw2={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 21}
    },
    ttl_urukul0_sw3={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 22}
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


device_db["spi_zotino0"] = {
    "type": "local",
    "module": "artiq.coredevice.spi2",
    "class": "SPIMaster",
    "arguments": {"channel": 23}
}
device_db["ttl_zotino0_ldac"] = {
    "type": "local",
    "module": "artiq.coredevice.ttl",
    "class": "TTLOut",
    "arguments": {"channel": 24}
}
device_db["ttl_zotino0_clr"] = {
    "type": "local",
    "module": "artiq.coredevice.ttl",
    "class": "TTLOut",
    "arguments": {"channel": 25}
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
