from operator import add
from functools import reduce

from migen import *


class Delay(Module):
    def __init__(self, i, delay, o=None):
        if isinstance(i, (int, tuple)):
            z = [Signal(i) for j in range(delay + 1)]
        elif isinstance(i, list):
            z = [Record(i) for j in range(delay + 1)]
        elif isinstance(i, Record):
            z = [Record(i.layout) for j in range(delay + 1)]
        else:
            z = [Signal.like(i) for j in range(delay + 1)]
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
    """Signed saturating addition mixin"""
    def sat_add(self, *a, limits=None, clipped=None):
        a = list(a)
        # assert all(value_bits_sign(ai)[1] for ai in a)
        length = max(len(ai) for ai in a)
        carry = log2_int(len(a), need_pow2=False)
        full = Signal((length + carry, True))
        limited = Signal((length, True))
        if clipped is None:
            clipped = Signal(2)
        self.comb += [
            full.eq(reduce(add, a)),
        ]
        if limits is None:
            self.comb += [
                If(full[-1-carry:] == Replicate(full[-1], carry + 1),
                    limited.eq(full),
                    clipped.eq(0),
                ).Else(
                    limited.eq(Cat(Replicate(~full[-1], length - 1), full[-1])),
                    clipped.eq(Cat(full[-1], ~full[-1])),
                )
            ]
        else:
            self.comb += [
                clip.eq(Cat(full < limits[0], full > limits[1])),
                Case(clip, {
                    0b01, limited.eq(limits[0]),
                    0b10, limited.eq(limits[1]),
                    "default": limited.eq(full),
                })
            ]
        return limited
