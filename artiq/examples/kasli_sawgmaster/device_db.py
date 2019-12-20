core_addr = "192.168.1.70"

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

for i in range(8):
    device_db["ttl" + str(i)] = {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut" if i < 4 else "TTLOut",
        "arguments": {"channel": 1+i},
    }

device_db.update(
    spi_urukul0={
        "type": "local",
        "module": "artiq.coredevice.spi2",
        "class": "SPIMaster",
        "arguments": {"channel": 9}
    },
    ttl_urukul0_io_update={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 10}
    },
    ttl_urukul0_sw0={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 11}
    },
    ttl_urukul0_sw1={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 12}
    },
    ttl_urukul0_sw2={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 13}
    },
    ttl_urukul0_sw3={
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 14}
    },
    urukul0_cpld={
        "type": "local",
        "module": "artiq.coredevice.urukul",
        "class": "CPLD",
        "arguments": {
            "spi_device": "spi_urukul0",
            "io_update_device": "ttl_urukul0_io_update",
            "refclk": 150e6,
            "clk_sel": 2
        }
    }
)

for i in range(4):
    device_db["urukul0_ch" + str(i)] = {
        "type": "local",
        "module": "artiq.coredevice.ad9910",
        "class": "AD9910",
        "arguments": {
            "pll_n": 16,  # 600MHz sample rate
            "pll_vco": 2,
            "chip_select": 4 + i,
            "cpld_device": "urukul0_cpld",
            "sw_device": "ttl_urukul0_sw" + str(i)
        }
    }

"""
artiq_route routing.bin init
artiq_route routing.bin set 0 0
artiq_route routing.bin set 1 1 0
artiq_route routing.bin set 2 1 1 0
artiq_route routing.bin set 3 2 0
artiq_route routing.bin set 4 2 1 0
artiq_coremgmt -D kasli config write -f routing_table routing.bin
"""

for sayma in range(2):
    amc_base = 0x010000 + sayma*0x020000
    rtm_base = 0x020000 + sayma*0x020000
    for i in range(4):
        device_db["led" + str(4*sayma+i)] = {
            "type": "local",
            "module": "artiq.coredevice.ttl",
            "class": "TTLOut",
            "arguments": {"channel": amc_base + i}
        }
    for i in range(2):
        device_db["ttl_mcx" + str(2*sayma+i)] = {
            "type": "local",
            "module": "artiq.coredevice.ttl",
            "class": "TTLInOut",
            "arguments": {"channel": amc_base + 4 + i}
        }
    for i in range(8):
        device_db["sawg" + str(8*sayma+i)] = {
            "type": "local",
            "module": "artiq.coredevice.sawg",
            "class": "SAWG",
            "arguments": {"channel_base": amc_base + 6 + i*10, "parallelism": 4}
        }
    for basemod in range(2):
        for i in range(4):
            device_db["sawg_sw" + str(8*sayma+4*basemod+i)] = {
                "type": "local",
                "module": "artiq.coredevice.ttl",
                "class": "TTLOut",
                "arguments": {"channel": rtm_base + basemod*9 + i}
            }
        att_idx = 2*sayma + basemod
        device_db["basemod_att_rst_n"+str(att_idx)] = {
            "type": "local",
            "module": "artiq.coredevice.ttl",
            "class": "TTLOut",
            "arguments": {"channel": rtm_base + basemod*9 + 4}
        }
        device_db["basemod_att_clk"+str(att_idx)] = {
            "type": "local",
            "module": "artiq.coredevice.ttl",
            "class": "TTLOut",
            "arguments": {"channel": rtm_base + basemod*9 + 5}
        }
        device_db["basemod_att_le"+str(att_idx)] = {
            "type": "local",
            "module": "artiq.coredevice.ttl",
            "class": "TTLOut",
            "arguments": {"channel": rtm_base + basemod*9 + 6}
        }
        device_db["basemod_att_mosi"+str(att_idx)] = {
            "type": "local",
            "module": "artiq.coredevice.ttl",
            "class": "TTLOut",
            "arguments": {"channel": rtm_base + basemod*9 + 7}
        }
        device_db["basemod_att_miso"+str(att_idx)] = {
            "type": "local",
            "module": "artiq.coredevice.ttl",
            "class": "TTLInOut",
            "arguments": {"channel": rtm_base + basemod*9 + 8}
        }
        device_db["basemod_att"+str(att_idx)] = {
            "type": "local",
            "module": "artiq.coredevice.basemod_att",
            "class": "BaseModAtt",
            "arguments": {
                "rst_n": "basemod_att_rst_n"+str(att_idx),
                "clk": "basemod_att_clk"+str(att_idx),
                "le": "basemod_att_le"+str(att_idx),
                "mosi": "basemod_att_mosi"+str(att_idx),
                "miso": "basemod_att_miso"+str(att_idx),
            }
        }

