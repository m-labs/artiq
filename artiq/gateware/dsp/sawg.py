from migen import *
from misoc.interconnect.stream import Endpoint

from misoc.cores.cordic import Cordic
from .accu import PhasedAccu, Accu
from .tools import eqh, Delay
from .spline import Spline


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


class DDSFast(Module):
    def __init__(self, width, t_width=None,
                 a_width=None, p_width=None, f_width=None,
                 a_order=4, p_order=1, f_order=2, parallelism=8):
        if t_width is None:
            t_width = width
        if a_width is None:
            a_width = width + (a_order - 1)*t_width
        if p_width is None:
            p_width = width + (p_order - 1)*t_width
        if f_width is None:
            f_width = width + (f_order + 1)*t_width
        a = Spline(order=a_order, width=a_width)
        p = Spline(order=p_order, width=p_width)
        f = Spline(order=f_order, width=f_width)
        self.submodules += a, p, f

        self.a = a.tri(t_width)
        self.f = f.tri(t_width)
        self.p = p.tri(t_width)
        self.i = [self.a, self.f, self.p]
        self.o = [[Signal((width, True)) for i in range(2)]
                  for i in range(parallelism)]
        self.parallelism = parallelism
        self.latency = 0  # will be accumulated

        ###

        self.latency += p.latency
        q = PhasedAccu(f_width, parallelism)
        self.submodules += q
        self.latency += q.latency
        da = [Signal((width, True)) for i in range(q.latency)]

        self.sync += [
            If(q.i.stb & q.i.ack,
                eqh(da[0], a.o.a0),
                [da[i + 1].eq(da[i]) for i in range(len(da) - 1)],
            ),
            If(p.o.stb & p.o.ack,
                q.i.clr.eq(0),
            ),
            If(p.i.stb & p.i.ack,
                q.i.clr.eq(self.clr),
            ),
        ]
        self.comb += [
            a.o.ack.eq(self.ce),
            p.o.ack.eq(self.ce),
            f.o.ack.eq(self.ce),
            q.i.stb.eq(self.ce),
            eqh(q.i.p, p.o.a0),
            q.i.f.eq(f.o.a0),
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
                ci.xi.eq(da[-1]),
                ci.yi.eq(0),
                eqh(ci.zi, qoi),
                eqh(self.o[i][0], ci.xo),
                eqh(self.o[i][1], ci.yo),
            ]
        self.latency += c[0].latency
        self.gain = c[0].gain


class DDSSlow(Module):
    def __init__(self, width, t_width, a_width, p_width, f_width,
                 a_order=4, p_order=1, f_order=2):
        a = Spline(order=a_order, width=a_width)
        p = Spline(order=p_order, width=p_width)
        f = Spline(order=f_order, width=f_width)
        self.submodules += a, p, f

        self.a = a.tri(t_width)
        self.f = f.tri(t_width)
        self.p = p.tri(t_width)
        self.i = [self.a, self.f, self.p]
        self.i_names = "a f p".split()
        self.o = [Signal((width, True)) for i in range(2)]
        self.ce = Signal()
        self.clr = Signal()
        self.latency = 0  # will be accumulated

        ###

        self.latency += p.latency
        q = Accu(f_width)
        self.latency += q.latency
        da = CEInserter()(Delay)(width, q.latency)
        c = Cordic(width=width, widthz=p_width,
                   guard=None, eval_mode="pipelined")
        self.latency += c.latency
        self.gain = c.gain
        self.submodules += q, da, c

        self.sync += [
            If(p.o.stb & p.o.ack,
                q.i.clr.eq(0),
            ),
            If(p.i.stb & p.i.ack,
                q.i.clr.eq(self.clr),
            ),
        ]
        self.comb += [
            da.ce.eq(q.i.stb & q.i.ack),
            a.o.ack.eq(self.ce),
            p.o.ack.eq(self.ce),
            f.o.ack.eq(self.ce),
            q.i.stb.eq(self.ce),
            eqh(da.i, a.o.a0),
            eqh(q.i.p, p.o.a0),
            q.i.f.eq(f.o.a0),
            q.o.ack.eq(1),
            c.xi.eq(da.o),
            c.yi.eq(0),
            eqh(c.zi, q.o.z),
            eqh(self.o[0], c.xo),
            eqh(self.o[1], c.yo),
        ]


class DDS(Module):
    def __init__(self, width, t_width=None,
                 a_width=None, p_width=None, f_width=None,
                 a_order=4, p_order=1, f_order=2, parallelism=8):
        if t_width is None:
            t_width = width
        if a_width is None:
            a_width = width + (a_order - 1)*t_width
        if p_width is None:
            p_width = width + (p_order - 1)*t_width
        if f_width is None:
            f_width = width + (f_order + 1)*t_width
        self.b = [DDSSlow(width, t_width, a_width, p_width, f_width, a_order,
                          p_order, f_order) for i in range(2)]
        p = Spline(order=1, width=p_width)
        f = Spline(order=1, width=f_width)
        self.submodules += self.b, p, f

        self.f0 = f.tri(t_width)
        self.p0 = p.tri(t_width)
        self.i = [self.f0, self.p0]
        self.i_names = "f0 p0".split()
        for i, bi in enumerate(self.b):
            self.i += bi.i
            for ii in bi.i_names:
                self.i_names.append("{}{}".format(ii, i + 1))
            for j in "afp":
                setattr(self, "{}{}".format(j, i + 1), getattr(bi, j))
        self.o = [[Signal((width, True)) for i in range(2)]
                  for i in range(parallelism)]
        self.ce = Signal()
        self.clr = Signal()
        self.parallelism = parallelism
        self.latency = 0  # will be accumulated

        ###

        self.latency += self.b[0].latency  # TODO: f0/p0, q.latency delta
        q = PhasedAccu(f_width, parallelism)
        self.submodules += q

        self.sync += [
            If(p.o.stb & p.o.ack,
                q.i.clr.eq(0),
            ),
            If(p.i.stb & p.i.ack,
                q.i.clr.eq(self.clr),
            ),
        ]
        self.comb += [
            [bi.ce.eq(self.ce) for bi in self.b],
            [bi.clr.eq(self.clr) for bi in self.b],
            p.o.ack.eq(self.ce),
            f.o.ack.eq(self.ce),
            q.i.stb.eq(self.ce),
            eqh(q.i.p, p.o.a0),
            eqh(q.i.f, f.o.a0),
            q.o.ack.eq(1),
        ]
        x = self.sat_add(bi.o[0] for bi in self.b)
        y = self.sat_add(bi.o[1] for bi in self.b)

        c = []
        for i in range(parallelism):
            ci = Cordic(width=width, widthz=p_width,
                        guard=None, eval_mode="pipelined")
            self.submodules += ci
            c.append(ci)
            qoi = getattr(q.o, "z{}".format(i))
            self.comb += [
                ci.xi.eq(x),
                ci.yi.eq(y),
                eqh(ci.zi, qoi),
                eqh(self.o[i][0], ci.xo),
                eqh(self.o[i][1], ci.yo),
            ]
        self.latency += c[0].latency
        self.gain = self.b[0].gain * c[0].gain


class Config(Module):
    def __init__(self):
        self.cfg = Record([("tap", 5), ("clr", 1), ("iq", 2)])
        self.i = Endpoint(self.cfg.layout)
        self.ce = Signal()

        ###

        n = Signal(1 << len(self.i.tap))
        tap = Signal.like(self.i.tap)
        clk = Signal()
        clk0 = Signal()

        self.comb += [
            self.i.ack.eq(1),
            clk.eq(Array(n)[tap]),
        ]
        self.sync += [
            clk0.eq(clk),
            self.ce.eq(0),
            If(clk0 ^ clk,
                self.ce.eq(1),
            ),
            n.eq(n + 1),
            If(self.i.stb,
                n.eq(0),
                self.cfg.eq(self.i.payload),
            ),
        ]


class Channel(Module):
    def __init__(self, width=16, t_width=None, u_order=4, **kwargs):
        if t_width is None:
            t_width = width
        du = Spline(width=width + (u_order - 1)*t_width, order=u_order)
        da = DDS(width, t_width, **kwargs)
        cfg = Config()
        self.submodules += du, da, cfg
        self.i = [cfg.i, du.tri(t_width)] + da.i
        self.i_names = "cfg u".split() + da.i_names
        self.q_i = [Signal((width, True)) for i in range(da.parallelism)]
        self.q_o = [ai[1] for ai in da.o]
        self.o = [Signal((width, True)) for i in range(da.parallelism)]
        self.width = width
        self.parallelism = da.parallelism
        self.latency = da.latency + 1
        self.cordic_gain = da.gain

        ###

        # delay du to match da
        ddu = Delay((width, True), da.latency - du.latency)
        self.submodules += ddu
        self.comb += [
            ddu.i.eq(du.o.a0[-width:]),
            da.clr.eq(cfg.cfg.clr),
            da.ce.eq(cfg.ce),
            du.o.ack.eq(cfg.ce),
        ]
        # wire up outputs and q_{i,o} exchange
        for oi, ai, qi in zip(self.o, da.o, self.q_i):
            self.sync += [
                oi.eq(self.sat_add([
                    ddu.o +
                    # du.o.a0[-width:],
                    Mux(cfg.cfg.iq[0], ai[0], 0),
                    Mux(cfg.cfg.iq[1], qi, 0)])),
            ]

    def connect_q(self, buddy):
        for i, qi in enumerate(self.q_i):
            self.comb += qi.eq(buddy.q_o[i])
