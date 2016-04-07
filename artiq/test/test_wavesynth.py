# Copyright (C) 2014, 2015 Robert Jordens <jordens@gmail.com>

import unittest

from artiq.wavesynth import compute_samples


class TestSynthesizer(unittest.TestCase):
    program = [
        [
            # frame 0
            {
                # frame 0, segment 0, line 0
                "dac_divider": 1,
                "duration": 100,
                "channel_data": [
                    {
                        # channel 0
                        "dds": {"amplitude": [0.0, 0.0, 0.01],
                                "phase": [0.0, 0.0, 0.0005],
                                "clear": False}
                    }
                ],
                "trigger": True
            },
            {
                # frame 0, segment 0, line 1
                "dac_divider": 1,
                "duration": 100,
                "channel_data": [
                    {
                        # channel 0
                        "dds": {"amplitude": [49.5, 1.0, -0.01],
                                "phase": [0.0, 0.05, 0.0005],
                                "clear": False}
                    }
                ],
                "trigger": False
            },
        ],
        [
            # frame 1
            {
                # frame 1, segment 0, line 0
                "dac_divider": 1,
                "duration": 100,
                "channel_data": [
                    {
                        # channel 0
                        "dds": {"amplitude": [100.0, 0.0, -0.01],
                                "phase": [0.0, 0.1, -0.0005],
                                "clear": False}
                    }
                ],
                "trigger": True
            },
            {
                # frame 1, segment 0, line 1
                "dac_divider": 1,
                "duration": 100,
                "channel_data": [
                    {
                        # channel 0
                        "dds": {"amplitude": [50.5, -1.0, 0.01],
                                "phase": [0.0, 0.05, -0.0005],
                                "clear": False}
                    }
                ],
                "trigger": False
            }
        ],
        [
            # frame 2
            {
                # frame 2, segment 0, line 0
                "dac_divider": 1,
                "duration": 84,
                "channel_data": [
                    {
                        # channel 0
                        "dds": {"amplitude": [100.0],
                                "phase": [0.0, 0.05],
                                "clear": False}
                    }
                ],
                "trigger": True
            },
            {
                # frame 2, segment 1, line 0
                "dac_divider": 1,
                "duration": 116,
                "channel_data": [
                    {
                        # channel 0
                        "dds": {"amplitude": [100.0],
                                "phase": [0.0, 0.05],
                                "clear": True}
                    }
                ],
                "trigger": True
            }
        ]
    ]

    def setUp(self):
        self.dev = compute_samples.Synthesizer(1, self.program)
        self.t = list(range(600))

    def drive(self):
        s = self.dev
        y = []
        for f in 0, 2, None, 1:
            if f is not None:
                s.select(f)
            y += s.trigger()[0]
        x = list(range(600))
        return x, y

    def test_run(self):
        x, y = self.drive()

    @unittest.skip("manual/visual test")
    def test_plot(self):
        from matplotlib import pyplot as plt
        x, y = self.drive()
        plt.plot(x, y)
        plt.show()
