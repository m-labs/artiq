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
    def sat_add(self, a, width, limits=None, clipped=None):
        a = list(a)
        # assert all(value_bits_sign(ai)[1] for ai in a)
        max_width = max(value_bits_sign(ai)[0] for ai in a)
        carry = log2_int(len(a), need_pow2=False)
        full = Signal((max_width + carry, True))
        limited = Signal((width, True))
        carry = len(full) - width
        assert carry >= 0
        clip = Signal(2)
        sign = Signal()
        if clipped is not None:
            self.comb += clipped.eq(clip)
        self.comb += [
            full.eq(reduce(add, a)),
            sign.eq(full[-1]),
            limited.eq(full)
        ]
        if limits is None:
            self.comb += [
                If(full[-1-carry:] != Replicate(sign, carry + 1),
                    clip.eq(Cat(sign, ~sign)),
                    limited.eq(Cat(Replicate(~sign, width - 1), sign)),
                )
            ]
        else:
            self.comb += [
                If(full < limits[0],
                    clip.eq(0b01),
                    limited.eq(limits[0])
                ),
                If(full > limits[1],
                    clip.eq(0b10),
                    limited.eq(limits[1]),
                )
            ]
        return limited
