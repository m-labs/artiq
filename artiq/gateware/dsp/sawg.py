from migen import *
from misoc.interconnect.stream import Endpoint
from misoc.cores.cordic import Cordic

from .accu import PhasedAccu
from .tools import eqh


class DDSFast(Module):
    def __init__(self, width, parallelism=4):
        a_width = width
        p_width = width
        f_width = 2*width

        self.o = [Signal((width, True)) for i in range(parallelism)]

        self.width = width
        self.parallelism = parallelism
        self.latency = 1  # will be accumulated

        q = PhasedAccu(f_width, parallelism)
        self.submodules += q
        self.latency += q.latency

        self.a = Endpoint([("a", a_width)])
        self.f = Endpoint([("f", f_width)])
        self.p = Endpoint([("p", p_width)])
        self.i = [self.a, self.f, self.p]

        ###

        a = Signal.like(self.a.a)
        self.sync += [
            If(self.a.stb,
                a.eq(self.a.a)
            ),
            If(self.f.stb,
                eqh(q.i.f, self.f.f)
            ),
            q.i.clr.eq(0),
            If(self.p.stb,
                eqh(q.i.p, self.p.p),
                q.i.clr.eq(1)
            ),
            q.i.stb.eq(self.f.stb | self.p.stb),
        ]
        self.comb += [
            self.a.ack.eq(1),
            self.f.ack.eq(1),
            self.p.ack.eq(1),
            q.o.ack.eq(1),
        ]

        c = []
        for i in range(parallelism):
            ci = Cordic(width=width, widthz=p_width,
                        guard=None, eval_mode="pipelined")
            self.submodules += ci
            c.append(ci)
            qoi = getattr(q.o, "z{}".format(i))
            self.comb += [
                eqh(ci.xi, a),
                ci.yi.eq(0),
                eqh(ci.zi, qoi),
                eqh(self.o[i], ci.xo),
            ]
        self.latency += c[0].latency
        self.gain = c[0].gain
