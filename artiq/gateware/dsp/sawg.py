from collections import namedtuple

from migen import *
from misoc.interconnect.stream import Endpoint
from misoc.cores.cordic import Cordic

from .accu import PhasedAccu, Accu
from .tools import eqh, Delay, SatAddMixin
from .spline import Spline


_Widths = namedtuple("_Widths", "t a p f")
_Orders = namedtuple("_Orders", "a p f")


class ParallelDDS(Module):
    def __init__(self, widths, parallelism=1, a_delay=0):
        self.i = Endpoint([("x", widths.a), ("y", widths.a),
                           ("f", widths.f), ("p", widths.f), ("clr", 1)])
        self.parallelism = parallelism
        self.widths = widths

        ###

        accu = PhasedAccu(widths.f, parallelism)
        cordic = [Cordic(width=widths.a, widthz=widths.p, guard=None,
                         eval_mode="pipelined") for i in range(parallelism)]
        self.xo = [c.xo for c in cordic]
        self.yo = [c.yo for c in cordic]
        a_delay += accu.latency
        xy_delay = Delay(2*widths.a, max(0, a_delay))
        z_delay = Delay(parallelism*widths.p, max(0, -a_delay))
        self.submodules += accu, xy_delay, z_delay, cordic
        self.latency = max(0, a_delay) + cordic[0].latency
        self.gain = cordic[0].gain

        self.comb += [
            xy_delay.i.eq(Cat(self.i.x, self.i.y)),
            z_delay.i.eq(Cat(zi[-widths.p:]
                             for zi in accu.o.payload.flatten())),
            eqh(accu.i.p, self.i.p),
            accu.i.f.eq(self.i.f),
            accu.i.clr.eq(self.i.clr),
            accu.i.stb.eq(self.i.stb),
            self.i.ack.eq(accu.i.ack),
            accu.o.ack.eq(1),
            [Cat(c.xi, c.yi).eq(xy_delay.o) for c in cordic],
            Cat(c.zi for c in cordic).eq(z_delay.o),
        ]


class SplineParallelDUC(ParallelDDS):
    def __init__(self, widths, orders, **kwargs):
        p = Spline(order=orders.p, width=widths.p)
        f = Spline(order=orders.f, width=widths.f)
        self.f = f.tri(widths.t)
        self.p = p.tri(widths.t)
        self.submodules += p, f
        self.ce = Signal(reset=1)
        self.clr = Signal()
        super().__init__(widths._replace(p=len(self.p.a0), f=len(self.f.a0)),
                         **kwargs)
        self.latency += f.latency

        ###

        assert p.latency == f.latency

        self.comb += [
            p.o.ack.eq(self.ce),
            f.o.ack.eq(self.ce),
            eqh(self.i.f, f.o.a0),
            eqh(self.i.p, p.o.a0),
            self.i.stb.eq(p.o.stb | f.o.stb),
        ]

        assert p.latency == 1
        self.sync += [
            self.i.clr.eq(0),
            If(p.i.stb,
                self.i.clr.eq(self.clr),
            ),
        ]


class SplineParallelDDS(SplineParallelDUC):
    def __init__(self, widths, orders, **kwargs):
        a = Spline(order=orders.a, width=widths.a)
        self.a = a.tri(widths.t)
        self.submodules += a
        super().__init__(widths._replace(a=len(self.a.a0)),
                         orders, **kwargs)

        ###

        self.comb += [
            a.o.ack.eq(self.ce),
            eqh(self.i.x, a.o.a0),
            self.i.y.eq(0),
        ]


class Config(Module):
    def __init__(self, width):
        self.clr = Signal(4, reset=0b1111)
        self.iq_en = Signal(2, reset=0b01)
        self.limit = [[Signal((width, True), reset=-(1 << width - 1)),
                       Signal((width, True), reset=(1 << width - 1) - 1)]
                      for i in range(2)]
        self.i = Endpoint([("addr", bits_for(4 + 2*len(self.limit))),
                           ("data", 16)])
        self.ce = Signal()

        ###

        div = Signal(16, reset=0)
        n = Signal.like(div)
        pad = Signal()

        reg = Array([Cat(div, n), self.clr, self.iq_en, pad] +
                    sum(self.limit, []))

        self.comb += [
            self.i.ack.eq(1),
            self.ce.eq(n == 0),
        ]
        self.sync += [
            n.eq(n - 1),
            If(self.ce,
                n.eq(div),
            ),
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
        self.submodules.b = b = SplineParallelDUC(
            widths._replace(a=len(a1.xo[0])), orders,
            parallelism=parallelism, a_delay=-a1.latency)
        cfg = Config(widths.a)
        u = Spline(width=widths.a, order=orders.a)
        du = Delay(widths.a, a1.latency + b.latency - u.latency)
        self.submodules += cfg, u, du
        self.u = u.tri(widths.t)
        self.i = [cfg.i, self.u, a1.a, a1.f, a1.p, a2.a, a2.f, a2.p, b.f, b.p]
        self.i_names = "cfg u a1 f1 p1 a2 f2 p2 f0 p0".split()
        self.i_named = dict(zip(self.i_names, self.i))
        self.y_in = [Signal((width, True)) for i in range(parallelism)]
        self.o = [Signal((width, True)) for i in range(parallelism)]
        self.widths = widths
        self.orders = orders
        self.parallelism = parallelism
        self.latency = a1.latency + b.latency + 1
        self.cordic_gain = a1.gain*b.gain

        ###

        self.comb += [
            a1.ce.eq(cfg.ce),
            a2.ce.eq(cfg.ce),
            b.ce.eq(cfg.ce),
            u.o.ack.eq(cfg.ce),
            Cat(a1.clr, a2.clr, b.clr).eq(cfg.clr),
            b.i.x.eq(self.sat_add([a1.xo[0], a2.xo[0]])),
            b.i.y.eq(self.sat_add([a1.yo[0], a2.yo[0]])),
            eqh(du.i, u.o.a0),
        ]
        # wire up outputs and q_{i,o} exchange
        for o, x, y in zip(self.o, b.xo, self.y_in):
            self.sync += [
                o.eq(self.sat_add([
                    du.o,
                    Mux(cfg.iq_en[0], x, 0),
                    Mux(cfg.iq_en[1], y, 0)])),
            ]

    def connect_y(self, buddy):
        self.comb += Cat(buddy.y_in).eq(Cat(self.b.yo))
