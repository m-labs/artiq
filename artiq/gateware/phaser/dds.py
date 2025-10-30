from migen import *
from misoc.cores.duc import PhasedAccu, complex, RealComplexMultiplier, saturate
from misoc.cores.cossin import CosSinGen

from artiq.gateware.phaser.register import WO

from math import log2, ceil
from operator import add


class PipelinedAdder(Module):
    def __init__(self, regs):
        n_stage = ceil(log2(len(regs)))

        # deep copy to prevent deleting signals
        operands = regs.copy()
        accu = []
        for _ in range(n_stage):
            while len(operands) > 0:
                if len(operands) > 1:
                    a, b = operands.pop(0), operands.pop(0)
                    sum = Signal(value_bits_sign(a + b))
                    self.sync += sum.eq(a + b)
                else:
                    # delay 1 cycle to match latency
                    a = operands.pop(0)
                    sum = Signal.like(a)
                    self.sync += sum.eq(a)
                accu.append(sum)

            # prepare for next stage
            operands = accu.copy()
            accu = []

        assert len(operands) == 1
        self.o = operands[0]


class SingleToneDDS(Module):
    """
    IQ oscillator that generates n sample per cycle

    :param n: number of sample output per cycle
    :param f_width: width of frequency tuning word 
    :param p_width: width of phase offset word
    :param a_width: width of amplitude scale factor (signed)
    """

    def __init__(self, n, f_width, p_width, a_width, iq_width):
        self.f = Signal(f_width)
        self.p = Signal(p_width)
        self.a = Signal((a_width, True))
        self.clr = Signal(reset=1)

        self.source = [Record(complex(iq_width)) for _ in range(n)]

        # # #

        self.submodules.accu = accu = PhasedAccu(n, f_width, p_width)
        self.comb += [
            accu.f.eq(self.f),
            accu.p.eq(self.p),
            accu.clr.eq(self.clr),
        ]

        generators = []
        for i in range(n):
            if i & 1:
                share_lut = generators[i - 1].lut
            else:
                share_lut = None

            # CosSinGen output width = x + 1
            csg = CosSinGen(z=len(self.accu.z[0]), x=iq_width - 1, share_lut=share_lut)
            generators.append(csg)
            assert len(self.source[i].i) == len(csg.x)

            mul = RealComplexMultiplier(a_width, len(csg.x), iq_width)
            self.comb += mul.a.eq(self.a)
            self.submodules += csg, mul

            self.sync += [
                csg.z.eq(self.accu.z[i]),
                mul.b.i.eq(csg.x),
                mul.b.q.eq(csg.y),
                self.source[i].i.eq(mul.p.i),
                self.source[i].q.eq(mul.p.q),
            ]


class MultiToneDDS(Module):
    """
    Multitone IQ DDS that generate n sample per cycle

                    iq_width    iq_width
    SingleToneDDS0 ────/────┐  + carry bits            iq_width
        ...                 +──────/────── clipping ──────/────── self.sources
    SingleToneDDSX ─────────┘

    :param n: number of sample output per cycle
    :param f_width: width of frequency tuning word 
    :param p_width: width of phase offset word
    :param a_width: width of amplitude scale factor (signed)
    :param use_pipeline_adder: enable pipeline adder at the cost of latency
    """

    def __init__(
        self, n, tones, f_width, p_width, a_width, iq_width, use_pipeline_adder
    ):
        self.sources = [Record(complex(iq_width)) for _ in range(n)]
        self.reg_banks = []

        # # #

        ddss = [
            SingleToneDDS(n, f_width, p_width, a_width, iq_width) for _ in range(tones)
        ]
        self.submodules += ddss

        for i, src in enumerate(self.sources):
            if use_pipeline_adder:
                # increase latency by celi(log2(n)) cycles
                i_adder = PipelinedAdder([d.source[i].i for d in ddss])
                q_adder = PipelinedAdder([d.source[i].q for d in ddss])
                self.submodules += i_adder, q_adder
                self.sync += [
                    saturate(src.i, i_adder.o),
                    saturate(src.q, q_adder.o),
                ]
            else:
                self.sync += [
                    saturate(src.i, reduce(add, [d.source[i].i for d in ddss])),
                    saturate(src.q, reduce(add, [d.source[i].q for d in ddss])),
                ]

        for i, d in enumerate(ddss):
            self.reg_banks.append([
                (d.f, WO),
                (d.p, WO),
                (d.a, WO),
                (d.clr, WO),
            ])
