from functools import reduce
from operator import xor

from migen import *

from misoc.interconnect import stream


def K(x, y):
    return (y << 5) | x


@ResetInserter()
@CEInserter()
class _Scrambler(Module):
    def __init__(self, n_io, n_state=23, taps=[17, 22]):
        self.i = Signal(n_io)
        self.o = Signal(n_io)

        # # #

        state = Signal(n_state, reset=1)
        curval = [state[i] for i in range(n_state)]
        for i in reversed(range(n_io)):
            flip = reduce(xor, [curval[tap] for tap in taps])
            self.comb += self.o[i].eq(flip ^ self.i[i])
            curval.insert(0, flip)
            curval.pop()

        self.sync += state.eq(Cat(*curval[:n_state]))


class Scrambler(Module):
    def __init__(self, sync_interval=2**10):
        self.sink = sink = stream.Endpoint([("data", 32)])
        self.source = source = stream.Endpoint([("d", 32), ("k", 4)])

        # # #

        # Scrambler
        self.submodules.scrambler = scrambler = _Scrambler(32)

        # Insert K29.7 SYNC character every "sync_interval" cycles
        count = Signal(max=sync_interval)
        self.sync += If(source.ack, count.eq(count + 1))
        self.comb += [
            source.stb.eq(1),
            If(count == 0,
                scrambler.reset.eq(1),
                source.k.eq(0b1),
                source.d.eq(K(29, 7)),
            ).Else(
                If(sink.stb, scrambler.i.eq(sink.data)),
                source.k.eq(0),
                source.d.eq(scrambler.o),
                If(source.ack,
                    sink.ack.eq(1),
                    scrambler.ce.eq(1)
                )
            )
        ]


class Descrambler(Module):
    def __init__(self):
        self.sink = sink = stream.Endpoint([("d", 32), ("k", 4)])
        self.source = source = stream.Endpoint([("data", 32)])

        # # #

        # Descrambler
        self.submodules.descrambler = descrambler = _Scrambler(32)
        self.comb += descrambler.i.eq(sink.d)

        # Detect K29.7 SYNC character and synchronize Descrambler
        self.comb += \
            If(sink.stb,
                If((sink.k == 0b1) & (sink.d == K(29,7)),
                    sink.ack.eq(1),
                    descrambler.reset.eq(1)
                ).Else(
                    source.stb.eq(1),
                    source.data.eq(descrambler.o),
                    If(source.ack,
                        sink.ack.eq(1),
                        descrambler.ce.eq(1)
                    )
                )
            )
