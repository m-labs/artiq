"""
Implementation and management of scan objects.

A scan object (e.g. :class:`artiq.language.scan.LinearScan`) represents a
one-dimensional sweep of a numerical range. Multi-dimensional scans are
constructed by combining several scan objects.

Iterate on a scan object to scan it, e.g. ::

    for variable in self.scan:
        do_something(variable)

Iterating multiple times on the same scan object is possible, with the scan
yielding the same values each time. Iterating concurrently on the
same scan object (e.g. via nested loops) is also supported, and the
iterators are independent from each other.

Scan objects are supported both on the host and the core device.
"""

import random
import inspect

from artiq.language.core import *
from artiq.language.environment import NoDefault, DefaultMissing


__all__ = ["ScanObject",
           "NoScan", "LinearScan", "RandomScan", "ExplicitScan",
           "Scannable"]


class ScanObject:
    pass


class NoScan(ScanObject):
    """A scan object that yields a single value."""
    def __init__(self, value):
        self.value = value

    @portable
    def _gen(self):
        yield self.value

    @portable
    def __iter__(self):
        return self._gen()

    def __len__(self):
        return 1

    def describe(self):
        return {"ty": "NoScan", "value": self.value}


class LinearScan(ScanObject):
    """A scan object that yields a fixed number of evenly
    spaced values in a range."""
    def __init__(self, start, stop, npoints):
        self.start = start
        self.stop = stop
        self.npoints = npoints

    @portable
    def _gen(self):
        if self.npoints == 0:
            return
        if self.npoints == 1:
            yield self.start
        else:
            dx = (self.stop - self.start)/(self.npoints - 1)
            for i in range(self.npoints):
                yield i*dx + self.start

    @portable
    def __iter__(self):
        return self._gen()

    def __len__(self):
        return self.npoints

    def describe(self):
        return {"ty": "LinearScan",
                "start": self.start, "stop": self.stop,
                "npoints": self.npoints}


class RandomScan(ScanObject):
    """A scan object that yields a fixed number of randomly ordered evenly
    spaced values in a range."""
    def __init__(self, start, stop, npoints, seed=None):
        self.start = start
        self.stop = stop
        self.npoints = npoints
        self.sequence = list(LinearScan(start, stop, npoints))
        if seed is None:
            rf = random.random
        else:
            rf = Random(seed).random
        random.shuffle(self.sequence, rf)

    @portable
    def __iter__(self):
        return iter(self.sequence)

    def __len__(self):
        return self.npoints

    def describe(self):
        return {"ty": "RandomScan",
                "start": self.start, "stop": self.stop,
                "npoints": self.npoints}


class ExplicitScan(ScanObject):
    """A scan object that yields values from an explicitly defined sequence."""
    def __init__(self, sequence):
        self.sequence = sequence

    @portable
    def __iter__(self):
        return iter(self.sequence)

    def __len__(self):
        return len(self.sequence)

    def describe(self):
        return {"ty": "ExplicitScan", "sequence": self.sequence}


_ty_to_scan = {
    "NoScan": NoScan,
    "LinearScan": LinearScan,
    "RandomScan": RandomScan,
    "ExplicitScan": ExplicitScan
}


class Scannable:
    """An argument (as defined in :class:`artiq.language.environment`) that
    takes a scan object.

    For arguments with units, use both the unit parameter (a string for
    display) and the scale parameter (a numerical scale for experiments).

    :param global_min: The minimum value taken by the scanned variable, common
        to all scan modes. The user interface takes this value to set the
        range of its input widgets.
    :param global_max: Same as global_min, but for the maximum value.
    :param global_step: The step with which the value should be modified by
        up/down buttons in a user interface. The default is the scale divided
        by 10.
    :param unit: A string representing the unit of the scanned variable, for
        display purposes only.
    :param scale: A numerical scaling factor by which the displayed values
        are multiplied when referenced in the experiment.
    :param ndecimals: The number of decimals a UI should use.
    """
    def __init__(self, default=NoDefault, unit="", scale=1.0,
                 global_step=None, global_min=None, global_max=None,
                 ndecimals=2):
        if global_step is None:
            global_step = scale/10.0
        if default is not NoDefault:
            self.default_value = default
        self.unit = unit
        self.scale = scale
        self.global_step = global_step
        self.global_min = global_min
        self.global_max = global_max
        self.ndecimals = ndecimals

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
        if hasattr(self, "default_value"):
            d["default"] = self.default_value.describe()
        d["unit"] = self.unit
        d["scale"] = self.scale
        d["global_step"] = self.global_step
        d["global_min"] = self.global_min
        d["global_max"] = self.global_max
        d["ndecimals"] = self.ndecimals
        return d
