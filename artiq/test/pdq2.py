import unittest
import os
import io

from artiq.devices.pdq2.driver import Pdq2


pdq2_source = os.getenv("ARTIQ_PDQ2_SOURCE")


class TestPdq2(unittest.TestCase):
    def setUp(self):
        self.dev = Pdq2(dev=io.BytesIO())

    def test_reset(self):
        self.dev.cmd("RESET", True)
        buf = self.dev.dev.getvalue()
        self.assertEqual(buf, b"\xa5\x00")

    def test_program(self):
        # about 0.14 ms
        self.dev.program(_test_program)

    @unittest.skipUnless(pdq2_source, "no pdq2 source and gateware")
    def test_gateware(self):
        self.dev.cmd("START", False)
        self.dev.cmd("ARM", False)
        self.dev.program(_test_program)
        self.dev.cmd("START", True)
        self.dev.cmd("ARM", True)
        #self.dev.cmd("TRIGGER", True)
        buf = self.dev.dev.getvalue()
        import sys
        sys.path.append(pdq2_source)
        from gateware.pdq2 import Pdq2Sim
        from migen.sim.generic import run_simulation
        from matplotlib import pyplot as plt
        import numpy as np
        tb = Pdq2Sim(buf)
        tb.ctrl_pads.trigger.reset = 0
        run_simulation(tb, vcd_name="pdq2.vcd", ncycles=len(buf) + 250)
        out = np.array(tb.outputs, np.uint16).view(np.int16)
        for outi in out[len(buf) + 100:].T:
            plt.step(np.arange(len(outi)), outi)
        plt.show()


_test_program = [
    [
        {
            "duration": 20,
            "channel_data": [
                {"bias": {"amplitude": [0, 0, 2e-3]}},
                {"bias": {"amplitude": [1, 0, -7.5e-3, 7.5e-4]}},
                {"dds": {
                    "amplitude": [0, 0, 4e-3, 0],
                    "phase": [.5, .05],
                }},
            ],
        },
        {
            "duration": 40,
            "channel_data": [
                {"bias": {"amplitude": [.4, .04, -2e-3]}},
                {"bias": {
                    "amplitude": [.5],
                    "silence": True,
                }},
                {"dds": {
                    "amplitude": [.8, .08, -4e-3, 0],
                    "phase": [.5, .05, .04/40],
                    "clear": True,
                }},
            ],
        },
        {
            "duration": 20,
            "channel_data": [
                {"bias": {"amplitude": [.4, -.04, 2e-3]}},
                {"bias": {"amplitude": [.5, 0, -7.5e-3, 7.5e-4]}},
                {"dds": {
                    "amplitude": [.8, -.08, 4e-3, 0],
                    "phase": [-.5],
                }},
            ],
            "wait_trigger": True,
            "jump": True,
        },
    ]
]
