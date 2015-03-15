from copy import copy
from math import cos, pi

import cairoplot


class Spline:
    def __init__(self, c):
        self.set_coefficients(c)

    def set_coefficients(self, c):
        self.c = copy(c)

    def next(self):
        r = self.c[0]
        for i in range(len(self.c)-1):
            self.c[i] += self.c[i+1]
        return r


class SplinePhase:
    def __init__(self, c):
        self.c = [0.0]
        self.set_coefficients(c)

    def clear(self):
        self.c[0] = 0.0

    def set_coefficients(self, c):
        self.c = self.c[0:1] + c[1:]
        self.c0 = self.c[0]

    def next(self):
        r = self.c[0] + self.c0
        for i in range(len(self.c)-1):
            self.c[i] += self.c[i+1] % 1.0
        return r


class DDS:
    def __init__(self, c_amplitude, c_phase):
        self.amplitude = Spline(c_amplitude)
        self.phase = SplinePhase(c_phase)

    def next(self):
        return self.amplitude.next()*cos(2*pi*self.phase.next())


class Wave:
    def __init__(self, c_bias, c_dds_amplitude, c_dds_phase):
        self.bias = Spline(c_bias)
        self.dds = DDS(c_dds_amplitude, c_dds_phase)

    def next(self):
        return self.bias.next() + self.dds.next()


if __name__ == "__main__":
    w = Wave([0.0, 0.0, 0.0], [0.0, 0.0, 0.01], [0.0, 0.0, 0.0005])
    x = list(range(400))
    y = [w.next() for i in range(100)]
    w.dds.amplitude.c[2] = -0.01
    y += [w.next() for i in range(100)]
    w.dds.amplitude.c[2] = -0.01
    w.dds.phase.c[2] = -0.0005
    y += [w.next() for i in range(100)]
    w.dds.amplitude.c[2] = 0.01
    y += [w.next() for i in range(100)]
    cairoplot.scatter_plot("plot.png", [x, y])
