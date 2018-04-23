import logging
import string
import unittest

from migen import *
from migen.genlib import io

from artiq.gateware.suservo.adc_ser import ADC, ADCParams


class DDROutputImpl(Module):
    def __init__(self, i1, i2, o, clk):
        do_clk0 = Signal(reset_less=True)
        do_j1 = Signal(reset_less=True)
        do_j2 = Signal(reset_less=True)
        do_j3 = Signal(reset_less=True)
        self.sync.async += [
                do_clk0.eq(clk),
                do_j1.eq(i1),
                do_j2.eq(i2),
                If(Cat(do_clk0, clk) == 0b10,
                    o.eq(do_j1),
                    do_j3.eq(do_j2),
                ).Elif(Cat(do_clk0, clk) == 0b01,
                    o.eq(do_j3),
                )
        ]


class DDROutput:
    @staticmethod
    def lower(dr):
        return DDROutputImpl(dr.i1, dr.i2, dr.o, dr.clk)


class DDRInputImpl(Module):
    def __init__(self, i, o1, o2, clk):
        di_clk0 = Signal(reset_less=True)
        # SAME_EDGE_PIPELINED is effectively one register for o1
        # (during rising clock)
        di_j1 = Signal(reset_less=True)
        di_j2 = Signal(reset_less=True)
        di_j3 = Signal(reset_less=True)
        self.sync.async += [
                di_clk0.eq(clk),
                di_j1.eq(i),
                If(Cat(di_clk0, clk) == 0b10,
                    di_j3.eq(di_j1),
                    o1.eq(di_j3),
                    o2.eq(di_j2)
                ).Elif(Cat(di_clk0, clk) == 0b01,
                    di_j2.eq(di_j1)
                )
        ]


class DDRInput:
    @staticmethod
    def lower(dr):
        return DDRInputImpl(dr.i, dr.o1, dr.o2, dr.clk)


class TB(Module):
    def __init__(self, params):
        self.params = p = params

        self.sck = Signal()
        self.clkout = Signal(reset_less=True)
        self.cnv_b = Signal()

        self.sck_en = Signal()
        self.sck_en_ret = Signal()

        adc_sck_en = Signal()
        cd_adc = ClockDomain("adc", reset_less=True)
        self.clock_domains += cd_adc

        self.sdo = []
        self.data = [Signal((p.width, True), reset_less=True)
                for i in range(p.channels)]

        srs = []
        for i in range(p.lanes):
            name = "sdo" + string.ascii_lowercase[i]
            sdo = Signal(name=name, reset_less=True)
            self.sdo.append(sdo)
            setattr(self, name, sdo)
            sr = Signal(p.width*p.channels//p.lanes, reset_less=True)
            srs.append(sr)
            self.specials += io.DDROutput(
                    # one for async
                    self._dly(sr[-1], -1), self._dly(sr[-2], -1), sdo)
            self.sync.adc += [
                    If(adc_sck_en,
                        sr[2:].eq(sr)
                    )
            ]
            cnv_b_old = Signal(reset_less=True)
            self.sync.async += [
                    cnv_b_old.eq(self.cnv_b),
                    If(Cat(cnv_b_old, self.cnv_b) == 0b10,
                        sr.eq(Cat(reversed(self.data[2*i:2*i + 2]))),
                    )
            ]

        adc_clk_rec = Signal()
        self.comb += [
                adc_sck_en.eq(self._dly(self.sck_en, 1)),
                self.sck_en_ret.eq(self._dly(adc_sck_en)),
                adc_clk_rec.eq(self._dly(self.sck, 1)),
                self.clkout.eq(self._dly(adc_clk_rec)),
        ]

    def _dly(self, sig, n=0):
        n += self.params.t_rtt*4//2 # t_{sys,adc,ret}/t_async half rtt
        dly = Signal(n, reset_less=True)
        self.sync.async += dly.eq(Cat(sig, dly))
        return dly[-1]


def main():
    params = ADCParams(width=8, channels=4, lanes=2,
            t_cnvh=3, t_conv=5, t_rtt=4)
    tb = TB(params)
    adc = ADC(tb, params)
    tb.submodules += adc

    def run(tb):
        dut = adc
        for i, ch in enumerate(tb.data):
            yield ch.eq(i)
        assert (yield dut.done)
        yield dut.start.eq(1)
        yield
        yield dut.start.eq(0)
        yield
        assert not (yield dut.done)
        while not (yield dut.done):
            yield
        x = (yield from [(yield d) for d in dut.data])
        for i, ch in enumerate(x):
            assert ch == i, (hex(ch), hex(i))

    run_simulation(tb, [run(tb)],
            vcd_name="adc.vcd",
            clocks={
                "sys":   (8, 0),
                "adc":   (8, 0),
                "ret":   (8, 0),
                "async": (2, 0),
            },
            special_overrides={
                io.DDROutput: DDROutput,
                io.DDRInput: DDRInput
            })


class ADCTest(unittest.TestCase):
    def test_run(self):
        main()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
