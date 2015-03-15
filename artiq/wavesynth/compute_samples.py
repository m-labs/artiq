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
        self.c0 = self.c[0]

    def clear(self):
        self.c[0] = 0.0

    def next(self):
        r = self.c[0] + self.c0
        for i in range(len(self.c)-1):
            self.c[i] += self.c[i+1] % 1.0
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


if __name__ == "__main__":
    x = list(range(400))
    w = Wave()

    w.dds.amplitude.set_coefficients([0.0, 0.0, 0.01])
    w.dds.phase.set_coefficients([0.0, 0.0, 0.0005])
    y = [w.next() for i in range(100)]

    w.dds.amplitude.set_coefficients([49.5, 1.0, -0.01])
    y += [w.next() for i in range(100)]

    w.dds.phase.set_coefficients([0.0, 0.1, -0.0005])
    y += [w.next() for i in range(100)]

    w.dds.amplitude.set_coefficients([50.5, -1.0, 0.01])
    y += [w.next() for i in range(100)]

    cairoplot.scatter_plot("plot.png", [x, y])
