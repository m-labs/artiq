from math import floor
from operator import add
from functools import reduce
from collections import namedtuple

import numpy as np

from migen import *


def halfgen4(width, n, df=1e-3):
    """
    http://recycle.lbl.gov/~ldoolitt/halfband

    params:
        * `up` is the passband/stopband width, as a fraction of
          input sampling rate
        * `n is the order of half-band filter to generate
    returns:
        * `a` is the full set of FIR coefficients, `4*n-1` long.
          implement wisely.
    """

    npt = n*40
    wmax = 2*np.pi*width
    wfit = (1 - np.linspace(0, 1, npt)[:, None]**2)*wmax

    target = .5*np.ones_like(wfit)
    basis = np.cos(wfit*np.arange(1, 2*n, 2))
    weight = np.ones_like(wfit)

    f0 = None

    for i in range(40):
        l = np.linalg.pinv(basis*weight)@(target*weight)
        err = np.fabs(basis@l - .5)
        f = np.max(err)/np.mean(err)
        if f0 and (f0 - f)/(f0 + f) < df/2:
            break
        f0 = f
        weight[err > (1 - df)*np.max(err)] *= 1 + 1.5/(i + 11)
    a = np.c_[l, np.zeros_like(l)].ravel()[:-1]
    a = np.r_[a[::-1], 1, a]/2
    return a


_Widths = namedtuple("_Widths", "A B P")

_widths = {
    "DSP48E1": _Widths(25, 18, 48),
}


class ParallelFIR(Module):
    """Full-rate parallelized finite impulse response filter.

    Tries to use transposed form as much as possible.

    :param coefficients: tap coefficients (normalized to 1.),
        increasing delay.
    :param parallelism: number of samples per cycle.
    :param width: bit width of input and output.
    :param arch: architecture (default: "DSP48E1").
    """
    def __init__(self, coefficients, parallelism, width=16,
                 arch="DSP48E1", cull_delays=()):
        self.width = width
        self.parallelism = p = parallelism
        n = len(coefficients)
        # input and output: old to new, decreasing delay
        self.i = [Signal((width, True)) for i in range(p)]
        self.o = [Signal((width, True), reset_less=True) for i in range(p)]
        self.latency = (n + 1)//2//p + 2
        w = _widths[arch]

        c_max = max(abs(c) for c in coefficients)
        c_shift = bits_for(floor((1 << w.B - 2) / c_max))
        self.coefficients = cs = [int(round(c*(1 << c_shift)))
                                  for c in coefficients]
        assert max(bits_for(c) for c in cs) <= w.B
        max_out = sum(abs(c)*(1 << w.A - 1) for c in cs)
        assert max_out <= (1 << w.P - 1) - 1, (bits_for(max_out), w)

        ###

        # Delay line: increasing delay
        x = [Signal((w.A, True), reset_less=True) for _ in range(n + p - 1)]

        for xi, xj in zip(x, self.i[::-1]):
            self.comb += xi.eq(xj)
        for xi, xj in zip(x[len(self.i):], x):
            self.sync += xi.eq(xj)

        for delay in range(p):
            o = Signal((w.P, True), reset_less=True)
            self.sync += self.o[delay].eq(o >> c_shift)
            # Make products
            tap = delay
            for i, c in enumerate(cs):
                # simplify for halfband and symmetric filters
                if not c or c in cs[:i]:
                    continue
                js = [j + p - 1 for j, cj in enumerate(cs) if cj == c]
                m = Signal.like(o)
                o0, o = o, Signal.like(o)
                q = Signal.like(x[0])
                if tap + p <= js[0]:
                    self.sync += o0.eq(o + m)
                    tap += p
                else:
                    self.comb += o0.eq(o + m)
                assert min(js) - tap >= 0
                js = [j for j in js
                        if (p - 1 - j - tap) % p not in cull_delays]
                if not js:
                    continue
                self.comb += q.eq(reduce(add, [x[j - tap] for j in js]))
                self.sync += m.eq(c*q)
            # symmetric rounding
            if c_shift > 1 and delay not in cull_delays:
                self.comb += o.eq((1 << c_shift - 1) - 1)


class FIR(ParallelFIR):
    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, parallelism=1, **kwargs)
        self.i = self.i[0]
        self.o = self.o[0]


def halfgen4_cascade(rate, width, order=None):
    """Generate coefficients for cascaded half-band filters.

    Coefficients are normalized to a gain of two per stage to compensate for
    the zero stuffing.

    :param rate: upsampling rate. power of two
    :param width: passband/stopband width in units of input sampling rate.
    :param order: highest order, defaults to :param:`rate`"""
    if order is None:
        order = rate
    coeff = []
    p = 1
    while p < rate:
        p *= 2
        coeff.append(2*halfgen4(width*p/rate/2, order*p//rate))
    return coeff


class ParallelHBFUpsampler(Module):
    """Parallel, power-of-two, half-band, cascading upsampler.

    Coefficients should be normalized to overall gain of 2
    (highest/center coefficient being 1)."""
    def __init__(self, coefficients, width=16, **kwargs):
        self.parallelism = 1  # accumulate
        self.latency = 0  # accumulate
        self.width = width
        self.i = Signal((width, True))

        ###

        i = [self.i]
        for coeff in coefficients:
            self.parallelism *= 2
            hbf = ParallelFIR(coeff, self.parallelism, width=width,
                    cull_delays={0}, **kwargs)
            self.submodules += hbf
            self.comb += [a.eq(b) for a, b in zip(hbf.i[1::2], i)]
            i = hbf.o
            self.latency += hbf.latency
        self.o = i
