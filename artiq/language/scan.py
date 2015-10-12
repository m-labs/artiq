"""
Implementation and management of scan objects.

A scan object (e.g. :class:`artiq.language.scan.LinearScan`) represents a
one-dimensional sweep of a numerical range. Multi-dimensional scans are
constructed by combining several scan objects.

Iterate on a scan object to scan it, e.g. ::

    for variable in self.scan:
        do_something(variable)

Iterating multiple times on the same scan object is possible, with the scan
restarting at the minimum value each time. Iterating concurrently on the
same scan object (e.g. via nested loops) is also supported, and the
iterators are independent from each other.

Scan objects are supported both on the host and the core device.
"""

from random import Random, shuffle
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
    """A scan object that yields a fixed number of increasing evenly
    spaced values in a range."""
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

    def __len__(self):
        return self.npoints

    def describe(self):
        return {"ty": "LinearScan",
                "min": self.min, "max": self.max, "npoints": self.npoints}


class RandomScan(ScanObject):
    """A scan object that yields a fixed number of randomly ordered evenly
    spaced values in a range."""
    def __init__(self, min, max, npoints, seed=0):
        self.min = min
        self.max = max
        self.npoints = npoints
        self.sequence = list(LinearScan(min, max, npoints))
        shuffle(self.sequence, Random(seed).random)

    @portable
    def __iter__(self):
        return iter(self.sequence)

    def __len__(self):
        return self.npoints

    def describe(self):
        return {"ty": "RandomScan",
                "min": self.min, "max": self.max, "npoints": self.npoints}


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

    :param global_min: The minimum value taken by the scanned variable, common
        to all scan modes. The user interface takes this value to set the
        range of its input widgets.
    :param global_max: Same as global_min, but for the maximum value.
    :param global_step: The step with which the value should be modified by
        up/down buttons in a user interface. The default is the scale divided
        by 10.
    :param unit: A string representing the unit of the scanned variable, for user
        interface (UI) purposes.
    :param scale: The scale of value for UI purposes. The corresponding SI
        prefix is shown in front of the unit, and the displayed value is
        divided by the scale.
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
