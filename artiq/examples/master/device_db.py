# This is an example device database that needs to be adapted to your setup.
# The RTIO channel numbers here are for NIST CLOCK on KC705.
# The list of devices here is not exhaustive.

core_addr = "kc705.lab.m-labs.hk"

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
    "core_dds": {
        "type": "local",
        "module": "artiq.coredevice.dds",
        "class": "DDSGroupAD9914",
        "arguments": {
            "sysclk": 3e9,
            "first_dds_bus_channel": 26,
            "dds_bus_count": 2,
            "dds_channel_count": 3
        }
    },

    "i2c_switch": {
        "type": "local",
        "module": "artiq.coredevice.i2c",
        "class": "PCA9548"
    },

    "ttl0": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 0},
        "comment": "This is a fairly long comment, shown as tooltip."
    },
    "ttl1": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 1},
        "comment": "Hello World"
    },
    "ttl2": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 2}
    },
    "ttl3": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut",
        "arguments": {"channel": 3}
    },

    "ttl4": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 4}
    },
    "ttl5": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 5}
    },
    "ttl6": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 6}
    },
    "ttl7": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut",
        "arguments": {"channel": 7}
    },


    "ttl_sma": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLInOut",
        "arguments": {"channel": 18}
    },
    "led": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 19}
    },

    "ttl_ams101_ldac": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 20}
    },
    "ttl_clock_la32_p": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLClockGen",
        "arguments": {"channel": 21}
    },

    "spi_ams101": {
        "type": "local",
        "module": "artiq.coredevice.spi",
        "class": "SPIMaster",
        "arguments": {"channel": 22}
    },

    "spi0": {
        "type": "local",
        "module": "artiq.coredevice.spi",
        "class": "SPIMaster",
        "arguments": {"channel": 23}
    },

    "dac0": {
        "type": "local",
        "module": "artiq.coredevice.ad5360",
        "class": "AD5360",
        "arguments": {"spi_device": "spi0", "ldac_device": "ttl0"}
    },

    "dds0": {
        "type": "local",
        "module": "artiq.coredevice.dds",
        "class": "DDSChannelAD9914",
        "arguments": {"bus_channel": 26, "channel": 0},
        "comment": "Comments work in DDS panel as well"
    },
    "dds1": {
        "type": "local",
        "module": "artiq.coredevice.dds",
        "class": "DDSChannelAD9914",
        "arguments": {"bus_channel": 26, "channel": 1}
    },
    "dds2": {
        "type": "local",
        "module": "artiq.coredevice.dds",
        "class": "DDSChannelAD9914",
        "arguments": {"bus_channel": 26, "channel": 2}
    },

    "qc_q1_0": {
        "type": "controller",
        # ::1 is the IPv6 localhost address. If this controller is running on a remote machine,
        # replace it with the IP or hostname of the machine. If using the hostname, make sure
        # that it always resolves to a network-visible IP address (see documentation).
        "host": "::1",
        "port": 4000,
        "command": "aqctl_pdq -p {port} --bind {bind} --simulation --dump qc_q1_0.bin"
    },
    "qc_q1_1": {
        "type": "controller",
        "host": "::1",
        "port": 4001,
        "command": "aqctl_pdq -p {port} --bind {bind} --simulation --dump qc_q1_1.bin"
    },
    "qc_q1_2": {
        "type": "controller",
        "host": "::1",
        "port": 4002,
        "command": "aqctl_pdq -p {port} --bind {bind} --simulation --dump qc_q1_2.bin"
    },
    "qc_q1_3": {
        "type": "controller",
        "host": "::1",
        "port": 4003,
        "command": "aqctl_pdq -p {port} --bind {bind} --simulation --dump qc_q1_3.bin"
    },
    "electrodes": {
        "type": "local",
        "module": "artiq.devices.pdq",
        "class": "CompoundPDQ",
        "arguments": {
            "pdq2_devices": ["qc_q1_0", "qc_q1_1", "qc_q1_2", "qc_q1_3"],
            "trigger_device": "ttl2",
            "frame_devices": ["ttl4", "ttl5", "ttl6"]
        }
    },

    "lda": {
        "type": "controller",
        "best_effort": True,
        "host": "::1",
        "port": 3253,
        "command": "aqctl_lda -p {port} --bind {bind} --simulation"
    },

    "camera_sim": {
        "type": "controller",
        "host": "::1",
        "port": 6283,
        "target_name": "camera_sim",
        "command": "python3 -m artiq.examples.remote_exec_controller"
    },
    "camera_sim_rexec": {
        "type": "controller_aux_target",
        "controller": "camera_sim",
        "target_name": "camera_sim_rexec"
    },


    "ttl_out": "ttl0",
    "ttl_out_serdes": "ttl0",

    "loop_out": "ttl0",
    "loop_in": "ttl3",
    "loop_clock_out": "ttl_clock_la32_p",
    "loop_clock_in": "ttl7",

    "pmt": "ttl3",
    "bd_dds": "dds0",
    "bd_sw": "ttl0",
    "bdd_dds": "dds1",
    "bdd_sw": "ttl1"
}
