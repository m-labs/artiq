from operator import add
from functools import reduce
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


class FIR(Module):
    """Full-rate finite impulse response filter.

    Tries to use transposed form (adder chain instead of adder tree)
    as much as possible.

    :param coefficients: integer taps, increasing delay.
    :param width: bit width of input and output.
    :param shift: scale factor (as power of two).
    """
    def __init__(self, coefficients, width=16, shift=None):
        self.width = width
        self.i = Signal((width, True))
        self.o = Signal((width, True))
        n = len(coefficients)
        self.latency = n//2 + 3

        ###

        if shift is None:
            shift = bits_for(sum(abs(c) for c in coefficients)) - 1

        # Delay line: increasing delay
        x = [Signal((width, True)) for _ in range(n)]
        self.sync += [xi.eq(xj) for xi, xj in zip(x, [self.i] + x)]

        o = Signal((width + shift + 1, True))
        self.comb += self.o.eq(o >> shift)
        delay = -1
        # Make products
        for i, c in enumerate(coefficients):
            # simplify for halfband and symmetric filters
            if not c or c in coefficients[:i]:
                continue
            js = [j for j, cj in enumerate(coefficients) if cj == c]
            m = Signal.like(o)
            o0, o = o, Signal.like(o)
            if delay < js[0]:
                self.sync += o0.eq(o + m)
                delay += 1
            else:
                self.comb += o0.eq(o + m)
            assert js[0] - delay >= 0
            self.sync += m.eq(c*reduce(add, [x[j - delay] for j in js]))
        # symmetric rounding
        if shift:
            self.comb += o.eq((1 << shift - 1) - 1)


class ParallelFIR(Module):
    """Full-rate parallelized finite impulse response filter.

    Tries to use transposed form as much as possible.

    :param coefficients: integer taps, increasing delay.
    :param parallelism: number of samples per cycle.
    :param width: bit width of input and output.
    :param shift: scale factor (as power of two).
    """
    def __init__(self, coefficients, parallelism, width=16, shift=None):
        self.width = width
        self.parallelism = p = parallelism
        n = len(coefficients)
        # input and output: old to new, decreasing delay
        self.i = [Signal((width, True)) for i in range(p)]
        self.o = [Signal((width, True)) for i in range(p)]
        self.latency = (n + 1)//2//p + 2
        # ... plus one sample

        ###

        if shift is None:
            shift = bits_for(sum(abs(c) for c in coefficients)) - 1

        # Delay line: increasing delay
        x = [Signal((width, True)) for _ in range(n + p - 1)]
        self.sync += [xi.eq(xj) for xi, xj in zip(x, self.i[::-1] + x)]

        for delay in range(p):
            o = Signal((width + shift + 1, True))
            self.comb += self.o[delay].eq(o >> shift)
            # Make products
            for i, c in enumerate(coefficients):
                # simplify for halfband and symmetric filters
                if not c or c in coefficients[:i]:
                    continue
                js = [j + p - 1 for j, cj in enumerate(coefficients)
                      if cj == c]
                m = Signal.like(o)
                o0, o = o, Signal.like(o)
                if delay + p <= js[0]:
                    self.sync += o0.eq(o + m)
                    delay += p
                else:
                    self.comb += o0.eq(o + m)
                assert js[0] - delay >= 0
                self.sync += m.eq(c*reduce(add, [x[j - delay] for j in js]))
            # symmetric rounding
            if shift:
                self.comb += o.eq((1 << shift - 1) - 1)


def halfgen4_cascade(rate, width, order=None):
    """Generate coefficients for cascaded half-band filters.

    :param rate: upsampling rate. power of two
    :param width: passband/stopband width in units of input sampling rate.
    :param order: highest order, defaults to :param:`rate`"""
    if order is None:
        order = rate
    coeff = []
    p = 1
    while p < rate:
        p *= 2
        coeff.append(halfgen4(width*p/rate/2, order*p//rate))
    return coeff


class ParallelHBFUpsampler(Module):
    """Parallel, power-of-two, half-band, cascading upsampler.

    Coefficients should be normalized to overall gain of 2
    (highest/center coefficient being 1)."""
    def __init__(self, coefficients, width=16, **kwargs):
        self.parallelism = 1
        self.latency = 0
        self.width = width
        self.i = Signal((width, True))

        ###

        i = [self.i]
        for coeff in coefficients:
            self.parallelism *= 2
            # assert coeff[len(coeff)//2 + 1] == 1
            hbf = ParallelFIR(coeff, self.parallelism, width, **kwargs)
            self.submodules += hbf
            self.comb += [a.eq(b) for a, b in zip(hbf.i[::2], i)]
            i = hbf.o
            self.latency += hbf.latency
        self.o = i
