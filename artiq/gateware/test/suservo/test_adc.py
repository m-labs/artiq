import logging
import string
import unittest

from migen import *
from migen.genlib import io

from artiq.gateware.suservo.adc_ser import ADC, ADCParams



class TB(Module):
    def __init__(self, params):
        self.params = p = params

        self.sck = Signal()
        self.clkout = Signal(reset_less=True)
        self.cnv = Signal()

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
            self.sync.adc += [
                    sdo.eq(self._dly(sr[-1], 0)),
                    If(adc_sck_en,
                        sr[1:].eq(sr)
                    )
            ]
            cnv_old = Signal(reset_less=True)
            self.sync.async += [
                    cnv_old.eq(self.cnv),
                    If(Cat(cnv_old, self.cnv) == 0b10,
                        sr.eq(Cat(reversed(self.data[2*i:2*i + 2]))),
                    )
            ]

        adc_clk_rec = Signal()
        self.comb += [
                adc_sck_en.eq(self._dly(self.sck_en, 0)),
                self.sck_en_ret.eq(self._dly(adc_sck_en)),

                adc_clk_rec.eq(self._dly(self.sck, 0)),
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
            )


class ADCTest(unittest.TestCase):
    def test_run(self):
        main()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
