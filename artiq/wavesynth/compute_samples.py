# Copyright (C) 2014, 2015 M-Labs Limited
# Copyright (C) 2014, 2015 Robert Jordens <jordens@gmail.com>

from copy import copy
from math import cos, pi

from artiq.wavesynth.coefficients import discrete_compensate


class Spline:
    def __init__(self):
        self.c = [0.0]

    def set_coefficients(self, c):
        if not c:
            c = [0.]
        self.c = copy(c)
        discrete_compensate(self.c)

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
        if not c:
            c = [0.]
        self.c0 = c[0]
        c1p = c[1:]
        discrete_compensate(c1p)
        self.c[1:] = c1p

    def clear(self):
        self.c[0] = 0.0

    def next(self):
        r = self.c[0]
        for i in range(len(self.c) - 1):
            self.c[i] += self.c[i + 1]
            self.c[i] %= 1.0
        return r + self.c0


class DDS:
    def __init__(self):
        self.amplitude = Spline()
        self.phase = SplinePhase()

    def next(self):
        return self.amplitude.next()*cos(2*pi*self.phase.next())


class Channel:
    def __init__(self):
        self.bias = Spline()
        self.dds = DDS()
        self.v = 0.
        self.silence = False

    def next(self):
        v = self.bias.next() + self.dds.next()
        if not self.silence:
            self.v = v
        return self.v

    def set_silence(self, s):
        self.silence = s


class TriggerError(Exception):
    pass


class Synthesizer:
    def __init__(self, nchannels, program):
        self.channels = [Channel() for _ in range(nchannels)]
        self.program = program
        # line_iter is None: "wait for segment selection" state
        # otherwise: iterator on the current position in the frame
        self.line_iter = None

    def select(self, selection):
        if self.line_iter is not None:
            raise TriggerError("a frame is already selected")
        self.line_iter = iter(self.program[selection])
        self.line = next(self.line_iter)

    def trigger(self):
        if self.line_iter is None:
            raise TriggerError("no frame selected")

        line = self.line
        if not line.get("trigger", False):
            raise TriggerError("segment is not triggered")

        r = [[] for _ in self.channels]
        while True:
            for channel, channel_data in zip(self.channels,
                                             line["channel_data"]):
                channel.set_silence(channel_data.get("silence", False))
                if "bias" in channel_data:
                    channel.bias.set_coefficients(
                        channel_data["bias"]["amplitude"])
                if "dds" in channel_data:
                    channel.dds.amplitude.set_coefficients(
                        channel_data["dds"]["amplitude"])
                    if "phase" in channel_data["dds"]:
                        channel.dds.phase.set_coefficients(
                            channel_data["dds"]["phase"])
                    if channel_data["dds"].get("clear", False):
                        channel.dds.phase.clear()

            if line.get("dac_divider", 1) != 1:
                raise NotImplementedError

            for channel, rc in zip(self.channels, r):
                for i in range(line["duration"]):
                    rc.append(channel.next())

            try:
                self.line = line = next(self.line_iter)
                if line.get("trigger", False):
                    return r
            except StopIteration:
                self.line_iter = None
                return r
