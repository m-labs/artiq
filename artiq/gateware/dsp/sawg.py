from collections import namedtuple

from migen import *
from misoc.interconnect.stream import Endpoint
from misoc.cores.cordic import Cordic

from .accu import PhasedAccu
from .tools import eqh, SatAddMixin
from .spline import Spline
from .fir import ParallelHBFUpsampler, halfgen4_cascade


_Widths = namedtuple("_Widths", "t a p f")
_Orders = namedtuple("_Orders", "a p f")


class SplineParallelDUC(Module):
    def __init__(self, widths, orders, parallelism=1, **kwargs):
        self.parallelism = parallelism
        self.widths = widths
        p = Spline(order=orders.p, width=widths.p)
        f = Spline(order=orders.f, width=widths.f)
        self.f = f.tri(widths.t)
        self.p = p.tri(widths.t)
        self.submodules += p, f
        self.ce = Signal(reset=1)
        self.clr = Signal()

        ###
        accu = PhasedAccu(len(self.f.a0), parallelism)
        cordic = [Cordic(width=widths.a, widthz=len(self.p.a0), guard=None,
                         eval_mode="pipelined") for i in range(parallelism)]
        self.submodules += accu, cordic

        self.xi = [c.xi for c in cordic]
        self.yi = [c.yi for c in cordic]
        self.xo = [c.xo for c in cordic]
        self.yo = [c.yo for c in cordic]
        self.latency = cordic[0].latency
        self.gain = cordic[0].gain
        self.f.latency += accu.latency + self.latency
        self.p.latency += accu.latency + self.latency

        ###

        assert p.latency == f.latency
        self.comb += [
            p.o.ack.eq(self.ce),
            f.o.ack.eq(self.ce),
            eqh(accu.i.f, f.o.a0),
            eqh(accu.i.p, p.o.a0),
            accu.i.stb.eq(p.o.stb | f.o.stb),
            accu.o.ack.eq(1),
            [eqh(c.zi, zi) for c, zi in
             zip(cordic, accu.o.payload.flatten())]
        ]

        assert p.latency == 1
        accu.i.clr.reset_less = True
        self.sync += [
            accu.i.clr.eq(0),
            If(p.i.stb,
                accu.i.clr.eq(self.clr),
            ),
        ]


class SplineParallelDDS(SplineParallelDUC):
    def __init__(self, widths, orders, **kwargs):
        a = Spline(order=orders.a, width=widths.a)
        self.a = a.tri(widths.t)
        self.submodules += a
        super().__init__(widths._replace(a=len(self.a.a0)), orders, **kwargs)

        self.a.latency += self.latency

        ###

        self.comb += [
            a.o.ack.eq(self.ce),
            [eqh(x, a.o.a0) for x in self.xi],
            [y.eq(0) for y in self.yi],
        ]
        del self.xi
        del self.yi


class Config(Module):
    def __init__(self, width, cordic_gain):
        self.clr = Signal(3, reset=0b111)
        self.iq_en = Signal(2, reset=0b01)
        self.limits = [[Signal((width, True)), Signal((width, True))]
                for i in range(2)]
        limit = (1 << width - 1) - 1
        limit_cordic = int(limit/cordic_gain)
        self.limits[0][0].reset = Constant(-limit, (width, True))
        self.limits[0][1].reset = Constant(limit, (width, True))
        self.limits[1][0].reset = Constant(-limit_cordic, (width, True))
        self.limits[1][1].reset = Constant(limit_cordic, (width, True))
        # TODO make persistent, add read-out/notification/clear
        self.clipped = [Signal(2) for i in range(2)]
        self.i = Endpoint([("addr", bits_for(4 + 2*len(self.limits) - 1)),
                           ("data", width)])
        assert len(self.i.addr) == 3
        self.ce = Signal()

        ###

        div = Signal(16, reset=0)
        n = Signal.like(div)

        self.comb += self.ce.eq(n == 0)
        self.sync += [
            n.eq(n - 1),
            If(self.ce,
                n.eq(div),
            )
        ]

        pad = Signal()

        reg = Array(sum(self.limits,
            [Cat(div, n), self.clr, self.iq_en, pad]))

        self.comb += self.i.ack.eq(1)
        self.sync += [
            If(self.i.stb,
                reg[self.i.addr].eq(self.i.data),
            ),
        ]


class Channel(Module, SatAddMixin):
    def __init__(self, width=16, parallelism=4, widths=None, orders=None):
        if orders is None:
            orders = _Orders(a=4, f=2, p=1)
        if widths is None:
            widths = _Widths(t=width, a=orders.a*width, p=orders.p*width,
                             f=(orders.f + 2)*width)

        self.submodules.a1 = a1 = SplineParallelDDS(widths, orders)
        self.submodules.a2 = a2 = SplineParallelDDS(widths, orders)
        coeff = halfgen4_cascade(parallelism, width=.4, order=8)
        hbf = [ParallelHBFUpsampler(coeff, width=width + 1) for i in range(2)]
        self.submodules.b = b = SplineParallelDUC(
            widths._replace(a=len(hbf[0].o[0]), f=widths.f - width), orders,
            parallelism=parallelism)
        cfg = Config(width, b.gain)
        u = Spline(width=widths.a, order=orders.a)
        self.submodules += cfg, u, hbf
        self.u = u.tri(widths.t)
        self.i = [cfg.i, self.u, a1.a, a1.f, a1.p, a2.a, a2.f, a2.p, b.f, b.p]
        self.i_names = "cfg u a1 f1 p1 a2 f2 p2 f0 p0".split()
        self.i_named = dict(zip(self.i_names, self.i))
        self.y_in = [Signal.like(b.yo[0]) for i in range(parallelism)]
        self.o = [Signal((width, True), reset_less=True)
                for i in range(parallelism)]
        self.widths = widths
        self.orders = orders
        self.parallelism = parallelism
        self.cordic_gain = a2.gain*b.gain

        self.u.latency += 1  # self.o
        b.p.latency += 1  # self.o
        b.f.latency += 1  # self.o
        a_latency_delta = hbf[0].latency + b.latency + 2  # hbf.i, self.o
        for a in a1, a2:
            a.a.latency += a_latency_delta
            a.p.latency += a_latency_delta
            a.f.latency += a_latency_delta

        self.latency = max(_.latency for _ in self.i[1:])
        for i in self.i[1:]:
            i.latency -= self.latency
            assert i.latency <= 0
        cfg.i.latency = 0

        ###

        self.comb += [
            a1.ce.eq(cfg.ce),
            a2.ce.eq(cfg.ce),
            b.ce.eq(cfg.ce),
            u.o.ack.eq(cfg.ce),
            Cat(b.clr, a1.clr, a2.clr).eq(cfg.clr),
            [i.eq(j) for i, j in zip(b.xi, hbf[0].o)],
            [i.eq(j) for i, j in zip(b.yi, hbf[1].o)],
        ]
        hbf[0].i.reset_less = True
        hbf[1].i.reset_less = True
        self.sync += [
            hbf[0].i.eq(self.sat_add((a1.xo[0], a2.xo[0]),
                width=len(hbf[0].i),
                limits=cfg.limits[1], clipped=cfg.clipped[1])),
            hbf[1].i.eq(self.sat_add((a1.yo[0], a2.yo[0]),
                width=len(hbf[1].i),
                limits=cfg.limits[1])),
        ]
        # wire up outputs and q_{i,o} exchange
        for o, x, y in zip(self.o, b.xo, self.y_in):
            o_offset = Signal.like(o)
            o_x = Signal.like(x)
            o_y = Signal.like(y)
            self.comb += [
                o_offset.eq(u.o.a0[-len(o):]),
                If(cfg.iq_en[0],
                    o_x.eq(x)
                ),
                If(cfg.iq_en[1],
                    o_y.eq(y)
                ),
            ]
            self.sync += [
                o.eq(self.sat_add((o_offset, o_x, o_y),
                    width=len(o),
                    limits=cfg.limits[0], clipped=cfg.clipped[0])),
            ]

    def connect_y(self, buddy):
        self.comb += [i.eq(j) for i, j in zip(buddy.y_in, self.b.yo)]
