from random import Random, shuffle
import inspect

from artiq.language.core import *
from artiq.language.environment import NoDefault, DefaultMissing


__all__ = ["NoScan", "LinearScan", "RandomScan", "ExplicitScan", "Scannable"]


class NoScan:
    def __init__(self, value):
        self.value = value

    @portable
    def _gen(self):
        yield self.value

    @portable
    def __iter__(self):
        return self._gen()

    def describe(self):
        return {"ty": "NoScan", "value": self.value}


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

    def describe(self):
        return {"ty": "LinearScan",
                "min": self.min, "max": self.max, "npoints": self.npoints}


class RandomScan:
    def __init__(self, min, max, npoints, seed=0):
        self.sequence = list(LinearScan(min, max, npoints))
        shuffle(self.sequence, Random(seed).random)

    @portable
    def __iter__(self):
        return iter(self.sequence)

    def describe(self):
        return {"ty": "RandomScan",
                "min": self.min, "max": self.max, "npoints": self.npoints}


class ExplicitScan:
    def __init__(self, sequence):
        self.sequence = sequence

    @portable
    def __iter__(self):
        return iter(self.sequence)

    def describe(self):
        return {"ty": "ExplicitScan", "sequence": self.sequence}


_ty_to_scan = {
    "NoScan": NoScan,
    "LinearScan": LinearScan,
    "RandomScan": RandomScan,
    "ExplicitScan": ExplicitScan
}


class Scannable:
    def __init__(self, global_min=None, global_max=None, global_step=None,
                 unit="", default=NoDefault):
        self.global_min = global_min
        self.global_max = global_max
        self.global_step = global_step
        self.unit = unit
        if default is not NoDefault:
            self.default_value = default

    def default(self):
        if not hasattr(self, "default_value"):
            raise DefaultMissing
        return self.default_value

    def process(self, x):
        cls = _ty_to_scan[x["ty"]]
        args = dict()
        for arg in inspect.getargspec(cls).args[1:]:
            if arg in x:
                args[arg] = x[arg]
        return cls(**args)

    def describe(self):
        d = {"ty": "Scannable"}
        d["global_min"] = self.global_min
        d["global_max"] = self.global_max
        d["global_step"] = self.global_step
        d["unit"] = self.unit
        if hasattr(self, "default_value"):
            d["default"] = self.default_value.describe()
        return d
