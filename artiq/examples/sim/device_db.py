device_db = {
    "core": {
        "type": "local",
        "module": "artiq.sim.devices",
        "class": "Core",
        "arguments": {}
    },
    "mains_sync": {
        "type": "local",
        "module": "artiq.sim.devices",
        "class": "Input",
        "arguments": {"name": "mains_sync"}
    },
    "pmt": {
        "type": "local",
        "module": "artiq.sim.devices",
        "class": "Input",
        "arguments": {"name": "pmt"}
    },
    "laser_cooling": {
        "type": "local",
        "module": "artiq.sim.devices",
        "class": "WaveOutput",
        "arguments": {"name": "laser_cooling"}
    },
    "spectroscopy": {
        "type": "local",
        "module": "artiq.sim.devices",
        "class": "WaveOutput",
        "arguments": {"name": "spectroscopy"}
    },
    "spectroscopy_b": {
        "type": "local",
        "module": "artiq.sim.devices",
        "class": "VoltageOutput",
        "arguments": {"name": "spectroscopy_b"}
    },
    "state_detection": {
        "type": "local",
        "module": "artiq.sim.devices",
        "class": "WaveOutput",
        "arguments": {"name": "state_detection"}
    },
}
