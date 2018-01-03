from functools import reduce
from operator import xor

from migen import *

from misoc.interconnect import stream


def K(x, y):
    return (y << 5) | x


@ResetInserter()
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
    def __init__(self, sync_interval=1024, enable=True):
        self.sink = sink = stream.Endpoint([("data", 32)])
        self.source = source = stream.Endpoint([("d", 32), ("k", 4)])

        # # #

        if enable:
            # scrambler
            scrambler = _Scrambler(32)
            self.submodules += scrambler
            self.comb += scrambler.i.eq(sink.data)

            # insert K.29.7 as sync character
            # every sync_interval cycles
            count = Signal(max=sync_interval)
            self.sync += count.eq(count + 1)
            self.comb += [
                If(count == 0,
                    scrambler.reset.eq(1),
                    source.stb.eq(1),
                    source.k[0].eq(1),
                    source.d[:8].eq(K(29, 7))
                ).Else(
                    sink.ack.eq(source.ack),
                    source.stb.eq(sink.stb),
                    source.d.eq(scrambler.o)
                )
            ]
        else:
            self.comb += [
                sink.connect(source, omit={"data"}),
                source.k.eq(0b0000),
                source.d.eq(sink.data)
            ]


class Descrambler(Module):
    def __init__(self, enable=True):
        self.sink = sink = stream.Endpoint([("d", 32), ("k", 4)])
        self.source = source = stream.Endpoint([("data", 32)])

        # # #

        if enable:
            # descrambler
            descrambler = _Scrambler(32)
            self.submodules += descrambler
            self.comb += descrambler.i.eq(sink.d)

            # detect K29.7 and synchronize descrambler
            self.comb += [
                descrambler.reset.eq(0),
                If((sink.k[0] == 1) &
                   (sink.d[:8] == K(29,7)),
                    sink.ack.eq(1),
                    descrambler.reset.eq(1)
                ).Else(
                    sink.ack.eq(source.ack),
                    source.stb.eq(sink.stb),
                    source.data.eq(descrambler.o)
                )
            ]
        else:
            self.comb += [
                sink.connect(source, omit={"d", "k"}),
                source.data.eq(sink.d)
            ]
