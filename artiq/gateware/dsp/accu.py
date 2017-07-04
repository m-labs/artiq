from migen import *
from misoc.interconnect.stream import Endpoint


class Accu(Module):
    def __init__(self, width, meta=[]):
        self.i = Endpoint([("p", width), ("f", width), ("clr", 1)])
        self.o = Endpoint([("z", width)])
        self.latency = 1

        ###

        f = Signal.like(self.i.f)
        p = Signal.like(self.i.p)
        self.comb += self.i.ack.eq(~self.o.stb | self.o.ack)
        self.sync += [
            If(self.o.ack,
                self.o.stb.eq(0),
            ),
            If(self.i.ack,
                self.o.stb.eq(1),
                If(self.i.stb,
                    self.o.z.eq(self.i.p + Mux(self.i.clr, 0, self.o.z + p)),
                    f.eq(self.i.f),
                    p.eq(self.i.f - self.i.p),
                ).Else(
                    self.o.z.eq(self.o.z + f),
                )
            )
        ]


class MCM(Module):
    def __init__(self, width, constants):
        n = len(constants)
        self.i = i = Signal(width)
        self.o = o = [Signal.like(self.i) for i in range(n)]

        ###

        # TODO: improve MCM
        assert range(n) == constants
        assert n <= 9

        if n > 0:
            self.comb += o[0].eq(0)
        if n > 1:
            self.comb += o[1].eq(i)
        if n > 2:
            self.comb += o[2].eq(i << 1)
        if n > 3:
            self.comb += o[3].eq(i + (i << 1))
        if n > 4:
            self.comb += o[4].eq(i << 2)
        if n > 5:
            self.comb += o[5].eq(i + (i << 2))
        if n > 6:
            self.comb += o[6].eq(o[3] << 1)
        if n > 7:
            self.comb += o[7].eq((i << 3) - i)
        if n > 8:
            self.comb += o[8].eq(i << 3)


class PhasedAccu(Module):
    def __init__(self, width, parallelism=8):
        self.i = Endpoint([("p", width), ("f", width), ("clr", 1)])
        self.o = Endpoint([("z{}".format(i), width) for i in
                           range(parallelism)])
        self.parallelism = parallelism
        self.latency = 2

        ###

        a = MCM(width, range(parallelism + 1))
        self.submodules += a
        z = [Signal(width, reset_less=True) for i in range(parallelism)]
        o = self.o.payload.flatten()
        load = Signal(reset_less=True)
        clr = Signal(reset_less=True)
        p = Signal.like(self.i.p)
        f = Signal.like(self.i.f, reset_less=True)
        fp = Signal.like(self.i.f)
        self.comb += [
            self.i.ack.eq(self.o.ack),
            a.i.eq(self.i.f),
        ]

        self.sync += [
            If(self.o.ack,
                self.o.stb.eq(0),
            ),
            If(~self.o.stb | self.o.ack,
                self.o.stb.eq(1),
                If(load,
                    load.eq(0),
                    [oi.eq(Mux(clr, 0, o[0] + fp) + zi)
                     for oi, zi in zip(o, z)],
                    fp.eq(f),
                ).Else(
                    [oi.eq(oi + fp) for oi in o],
                ),
            ),
            If(self.i.stb & self.i.ack,
                [zi.eq(self.i.p - Mux(self.i.clr, 0, p) + aoi)
                 for zi, aoi in zip(z, a.o)],
                clr.eq(self.i.clr),
                p.eq(self.i.p),
                f.eq(a.o[parallelism]),
                load.eq(1),
            ),
        ]
