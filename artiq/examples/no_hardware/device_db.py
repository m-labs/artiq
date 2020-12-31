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

    # Controllers
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

}
