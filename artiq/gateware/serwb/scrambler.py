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
    def __init__(self, sync_interval=1024):
        self.enable = Signal()
        self.sink = sink = stream.Endpoint([("data", 32)])
        self.source = source = stream.Endpoint([("d", 32), ("k", 4)])

        # # #

        # scrambler
        self.submodules.scrambler = scrambler = _Scrambler(32)

        # insert K.29.7 as sync character
        # every sync_interval cycles
        count = Signal(max=sync_interval)
        self.submodules.fsm = fsm = ResetInserter()(FSM(reset_state="DISABLE"))
        self.comb += fsm.reset.eq(~self.enable)
        fsm.act("DISABLE",
            sink.connect(source, omit={"data"}),
            source.k.eq(0b0000),
            source.d.eq(sink.data),
            NextState("SYNC")
        )
        fsm.act("SYNC",
            scrambler.reset.eq(1),
            source.stb.eq(1),
            source.k[0].eq(1),
            source.d[:8].eq(K(29, 7)),
            NextValue(count, 0),
            If(source.ack,
                NextState("DATA")
            )
        )
        fsm.act("DATA",
            scrambler.i.eq(sink.data),
            sink.ack.eq(source.ack),
            source.stb.eq(1),
            source.d.eq(scrambler.o),
            If(source.stb & source.ack,
                scrambler.ce.eq(1),
                NextValue(count, count + 1),
                If(count == (sync_interval - 1),
                    NextState("SYNC")
                )
            )
        )


class Descrambler(Module):
    def __init__(self):
        self.enable = Signal()
        self.sink = sink = stream.Endpoint([("d", 32), ("k", 4)])
        self.source = source = stream.Endpoint([("data", 32)])

        # # #

        # descrambler
        self.submodules.descrambler = descrambler = _Scrambler(32)
        self.comb += descrambler.i.eq(sink.d)

        # detect K29.7 and synchronize descrambler
        self.submodules.fsm = fsm = ResetInserter()(FSM(reset_state="DISABLE"))
        self.comb += fsm.reset.eq(~self.enable)
        fsm.act("DISABLE",
            sink.connect(source, omit={"d", "k"}),
            source.data.eq(sink.d),
            NextState("SYNC_DATA")
        )
        fsm.act("SYNC_DATA",
            If((sink.k[0] == 1) &
               (sink.d[:8] == K(29,7)),
                sink.ack.eq(1),
                descrambler.reset.eq(1)
            ).Else(
                sink.ack.eq(source.ack),
                source.stb.eq(sink.stb),
                source.data.eq(descrambler.o),
                If(source.stb & source.ack,
                    descrambler.ce.eq(1)
                )
            )
        )
