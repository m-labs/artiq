from random import Random, shuffle

from artiq.language.core import *


class LinearScan:
    def __init__(self, min, max, npoints):
        self.min = min
        self.max = max
        self.npoints = npoints

    @portable
    def _gen(self):
        r = self.max - self.min
        d = self.npoints - 1
        for i in range(self.npoints):
            yield r*i/d + self.min

    @portable
    def __iter__(self):
        return self._gen()


class RandomScan:
    def __init__(self, min, max, npoints, seed=0):
        self.sequence = list(LinearScan(min, max, npoints))
        shuffle(self.sequence, Random(seed).random)

    @portable
    def __iter__(self):
        return iter(self.sequence)


class ExplicitScan:
    def __init__(self, sequence):
        self.sequence = sequence

    @portable
    def __iter__(self):
        return iter(self.sequence)
