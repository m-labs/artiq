from copy import copy
from math import cos, pi

import cairoplot


class Spline:
    def __init__(self):
        self.c = [0.0]

    def set_coefficients(self, c):
        self.c = copy(c)

    def next(self):
        r = self.c[0]
        for i in range(len(self.c)-1):
            self.c[i] += self.c[i+1]
        return r


class SplinePhase:
    def __init__(self):
        self.c = [0.0]
        self.c0 = 0.0

    def set_coefficients(self, c):
        self.c = self.c[0:1] + c[1:]
        self.c0 = c[0]

    def clear(self):
        self.c[0] = 0.0

    def next(self):
        r = self.c[0] + self.c0
        for i in range(len(self.c)-1):
            self.c[i] = (self.c[i] + self.c[i+1]) % 1.0
        return r


class DDS:
    def __init__(self):
        self.amplitude = Spline()
        self.phase = SplinePhase()

    def next(self):
        return self.amplitude.next()*cos(2*pi*self.phase.next())


class Wave:
    def __init__(self):
        self.bias = Spline()
        self.dds = DDS()

    def next(self):
        return self.bias.next() + self.dds.next()


class TriggerError(Exception):
    pass


class Synthesizer:
    def __init__(self, nchannels, program):
        self.channels = [Wave() for _ in range(nchannels)]
        self.program = program 
        # line_iter is None: "wait for segment selection" state
        # otherwise: iterator on the current position in the segment
        self.line_iter = None

    def trigger(self, selection=None):
        if selection is None:
            if self.line_iter is None:
                raise TriggerError
        else:
            if self.line_iter is not None:
                raise TriggerError
            self.line_iter = iter(self.program[selection])

        r = [[] for _ in self.channels]
        while True:
            line = next(self.line_iter)

            if line["dac_divider"] != 1:
                raise NotImplementedError

            for channel, channel_data in zip(self.channels,
                                             line["channel_data"]):
                if "bias" in channel_data:
                    channel.bias.set_coefficients(channel_data["bias"])
                if "dds" in channel_data:
                    channel.dds.amplitude.set_coefficients(
                        channel_data["dds"]["amplitude"])
                    channel.dds.phase.set_coefficients(
                        channel_data["dds"]["phase"])
                    if channel_data["dds"]["clear"]:
                        channel.dds.phase.clear()

            for channel, rc in zip(self.channels, r):
                for i in range(line["duration"]):
                    rc.append(channel.next())

            if line["wait_trigger"] and line["jump"]:
                raise ValueError("Line cannot both jump and wait for trigger")
            if line["wait_trigger"]:
                return r
            if line["jump"]:
                self.line_iter = None
                return r

def main():
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
                "wait_trigger": False,
                "jump": False
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
                "wait_trigger": False,
                "jump": True
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
                "wait_trigger": False,
                "jump": False
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
                "wait_trigger": False,
                "jump": True
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
                "wait_trigger": True,
                "jump": False
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
                "wait_trigger": False,
                "jump": True
            }
        ]
    ]

    x = list(range(600))
    s = Synthesizer(1, program)

    r = s.trigger(0)
    y = r[0]
    r = s.trigger(2)
    y += r[0]
    r = s.trigger()
    y += r[0]
    r = s.trigger(1)
    y += r[0]
    cairoplot.scatter_plot("plot.png", [x, y])

if __name__ == "__main__":
    main()
