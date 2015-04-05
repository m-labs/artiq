from copy import copy
from math import cos, pi


class Spline:
    def __init__(self):
        self.c = [0.0]

    def set_coefficients(self, c):
        self.c = copy(c)

    def next(self):
        r = self.c[0]
        for i in range(len(self.c) - 1):
            self.c[i] += self.c[i + 1]
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
        for i in range(len(self.c) - 1):
            self.c[i] = (self.c[i] + self.c[i + 1]) % 1.0
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
        self.last = 0.
        self.silence = False

    def next(self):
        v = self.bias.next() + self.dds.next()
        if not self.silence:
            self.last = v
        return self.last


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

            if line.get("dac_divider", 1) != 1:
                raise NotImplementedError

            for channel, channel_data in zip(self.channels,
                                             line["channel_data"]):
                if "bias" in channel_data:
                    channel.bias.set_coefficients(channel_data["bias"]["amplitude"])
                if "dds" in channel_data:
                    channel.dds.amplitude.set_coefficients(
                        channel_data["dds"]["amplitude"])
                    if "phase" in channel_data["dds"]:
                        channel.dds.phase.set_coefficients(
                            channel_data["dds"]["phase"])
                    if channel_data["dds"].get("clear", False):
                        channel.dds.phase.clear()
                channel.silence = channel_data.get("silence", False)

            for channel, rc in zip(self.channels, r):
                for i in range(line["duration"]):
                    rc.append(channel.next())

            if line.get("wait_trigger", False):
                return r
            if line.get("jump", False):
                if not line.get("wait_trigger", False):
                    raise ValueError("Jumps should be with wait_trigger")
                try:
                    next(self.line_iter)
                    raise ValueError("Jump in the middle of a frame")
                except StopIteration:
                    pass
                self.line_iter = None
                return r


def main():
    from artiq.test.wavesynth import TestSynthesizer
    import cairoplot

    t = TestSynthesizer()
    t.setUp()
    x, y = t.drive()
    cairoplot.scatter_plot("plot.png", [x, y])


if __name__ == "__main__":
    main()
