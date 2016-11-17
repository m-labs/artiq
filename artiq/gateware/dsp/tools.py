from operator import add
from functools import reduce

from migen import *


class Delay(Module):
    def __init__(self, i, delay, o=None):
        if isinstance(i, (int, tuple)):
            z = [Signal(i, reset_less=True) for j in range(delay + 1)]
        elif isinstance(i, list):
            z = [Record(i) for j in range(delay + 1)]
        elif isinstance(i, Record):
            z = [Record(i.layout) for j in range(delay + 1)]
        else:
            z = [Signal.like(i, reset_less=True) for j in range(delay + 1)]
        self.i = z[0]
        self.o = z[-1]
        if not isinstance(i, (int, list, tuple)):
            self.comb += self.i.eq(i)
        if o is not None:
            self.comb += o.eq(self.o)
        self.latency = delay
        self.sync += [z[j + 1].eq(z[j]) for j in range(delay)]


def eqh(a, b):
    return a[-len(b):].eq(b[-len(a):])


class SatAddMixin:
    def sat_add(self, a):
        a = list(a)
        # assert all(value_bits_sign(ai)[1] for ai in a)
        n = max(len(ai) for ai in a)
        o = log2_int(len(a), need_pow2=False)
        s = Signal((n + o, True))
        s0 = Signal((n, True))
        z = Signal((1, True))
        self.comb += [
            s.eq(reduce(add, a, z)),
            s0[-1].eq(s[-1]),
            If(s[-o-1:] == Replicate(s[-1], o + 1),
                s0[:-1].eq(s[:n-1]),
            ).Else(
                s0[:-1].eq(Replicate(~s[-1], n - 1)),
            )
        ]
        return s0
