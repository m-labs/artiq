from random import Random


class LinearScan:
    def __init__(self, min, max, npoints):
        self.min = min
        self.max = max
        self.npoints = npoints

    def _gen(self):
        r = self.max - self.min
        d = self.npoints - 1
        for i in range(self.npoints):
            yield r*i/d + self.min

    def __iter__(self):
        return self._gen()


class RandomScan:
    def __init__(self, min, max, npoints, seed=0):
        self.min = min
        self.max = max
        self.npoints = npoints
        self.seed = 0
    
    def _gen(self):
        prng = Random(self.seed)
        r = self.max - self.min
        for i in range(self.npoints):
            yield prng.random()*r + self.min

    def __iter__(self):
        return self._gen()
