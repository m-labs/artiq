# Copyright (C) 2014, 2015 Robert Jordens <jordens@gmail.com>

import unittest
import os
import io

from artiq.devices.pdq2.driver import Pdq2
from artiq.wavesynth.compute_samples import Synthesizer


pdq2_gateware = os.getenv("ARTIQ_PDQ2_GATEWARE")


class TestPdq2(unittest.TestCase):
    def setUp(self):
        self.dev = Pdq2(dev=io.BytesIO())
        self.synth = Synthesizer(3, _test_program)

    def test_reset(self):
        self.dev.cmd("RESET", True)
        buf = self.dev.dev.getvalue()
        self.assertEqual(buf, b"\xa5\x00")

    def test_program(self):
        # about 0.14 ms
        self.dev.program(_test_program)

    def test_cmd_program(self):
        self.dev.cmd("ARM", False)
        self.dev.cmd("START", False)
        self.dev.program(_test_program)
        self.dev.cmd("START", True)
        self.dev.cmd("ARM", True)
        #self.dev.cmd("TRIGGER", True)
        return self.dev.dev.getvalue()

    def test_synth(self):
        s = self.synth
        s.select(0)
        y = s.trigger()
        return list(zip(*y))

    def run_gateware(self):
        import sys
        sys.path.append(pdq2_gateware)
        from gateware.pdq2 import Pdq2Sim
        from migen.sim.generic import run_simulation

        buf = self.test_cmd_program()
        tb = Pdq2Sim(buf)
        tb.ctrl_pads.trigger.reset = 1
        run_simulation(tb, ncycles=len(buf) + 250)
        delays = 7, 10, 30
        y = list(zip(*tb.outputs[len(buf) + 130:]))
        y = list(zip(*(yi[di:] for yi, di in zip(y, delays))))
        self.assertGreaterEqual(len(y), 80)
        self.assertEqual(len(y[0]), 3)
        return y

    @unittest.skipUnless(pdq2_gateware, "no pdq2 gateware")
    def test_run_compare(self):
        y_ref = self.test_synth()
        y = self.run_gateware()

        for i, (yi, yi_ref) in enumerate(zip(y, y_ref)):
            for j, (yij, yij_ref) in enumerate(zip(yi, yi_ref)):
                yij = yij*20./2**16
                if yij > 10:
                    yij -= 20
                self.assertAlmostEqual(yij, yij_ref, 2, "disagreement at "
                                       "t={}, c={}".format(i, j))

    @unittest.skipUnless(pdq2_gateware, "no pdq2 gateware")
    @unittest.skip("manual/visual test")
    def test_run_plot(self):
        from matplotlib import pyplot as plt
        import numpy as np
        y_ref = self.test_synth()
        y_ref = np.array(y_ref)
        y = self.run_gateware()
        y = np.array(y, dtype=np.uint16).view(np.int16)
        y = y*20./2**16
        plt.step(np.arange(len(y)), y)
        plt.step(np.arange(len(y_ref)), y_ref, "k")
        plt.show()


_test_program = [
    [
        {
            "trigger": True,
            "duration": 20,
            "channel_data": [
                {"bias": {"amplitude": [0, 0, 2e-3]}},
                {"bias": {"amplitude": [1, 0, -7.5e-3, 7.5e-4]}},
                {"dds": {
                    "amplitude": [0, 0, 4e-3, 0],
                    "phase": [.25, .025],
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
                    "phase": [.25, .025, .02/40],
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
                    "phase": [-.25],
                }},
            ],
        },
    ]
]
