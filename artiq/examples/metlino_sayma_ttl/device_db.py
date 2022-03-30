core_addr = "192.168.1.65"

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
    }
}

# master peripherals
for i in range(4):
    device_db["led" + str(i)] = {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": i},
}

# DEST#1 peripherals
amc_base = 0x070000
rtm_base = 0x020000

for i in range(4):
    device_db["led" + str(4+i)] = {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": amc_base + i},
    }

#DIO (EEM0) starting at RTIO channel 0x000056
for i in range(8):
    device_db["ttl" + str(i)] = {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": amc_base + 0x000056 + i},
    }

#DIO (EEM1) starting at RTIO channel 0x00005e
for i in range(8):
    device_db["ttl" + str(8+i)] = {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": amc_base + 0x00005e + i},
    }

device_db["fmcdio_dirctl_clk"] = {
    "type": "local",
    "module": "artiq.coredevice.ttl",
    "class": "TTLOut",
    "arguments": {"channel": amc_base + 0x000066}
}

device_db["fmcdio_dirctl_ser"] = {
    "type": "local",
    "module": "artiq.coredevice.ttl",
    "class": "TTLOut",
    "arguments": {"channel": amc_base + 0x000067}
}

device_db["fmcdio_dirctl_latch"] = {
    "type": "local",
    "module": "artiq.coredevice.ttl",
    "class": "TTLOut",
    "arguments": {"channel": amc_base + 0x000068}
}

device_db["fmcdio_dirctl"] = {
    "type": "local",
    "module": "artiq.coredevice.shiftreg",
    "class": "ShiftReg",
    "arguments": {"clk": "fmcdio_dirctl_clk",
                  "ser": "fmcdio_dirctl_ser",
                  "latch": "fmcdio_dirctl_latch"}
}
