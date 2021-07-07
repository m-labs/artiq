import logging
import unittest

from migen import *
from artiq.gateware.suservo import iir


def main():
    w_kasli = iir.IIRWidths(state=25, coeff=18, adc=16,
            asf=14, word=16, accu=48, shift=11,
            channel=3, profile=5, dly=8)
    w = iir.IIRWidths(state=17, coeff=16, adc=16,
            asf=14, word=16, accu=48, shift=11,
            channel=2, profile=1, dly=8)

    def run(dut):
        for i, ch in enumerate(dut.adc):
            yield ch.eq(i)
        for i, ch in enumerate(dut.ctrl):
            yield ch.en_iir.eq(1)
            yield ch.en_out.eq(1)
            yield ch.profile.eq(i)
        for i in range(1 << w.channel):
            yield from dut.set_state(i, i << 8, coeff="x1")
            yield from dut.set_state(i, i << 8, coeff="x0")
            for j in range(1 << w.profile):
                yield from dut.set_state(i,
                        (j << 1) | (i << 8), profile=j, coeff="y1")
                for k, l in enumerate("pow offset ftw0 ftw1".split()):
                    yield from dut.set_coeff(i, profile=j, coeff=l,
                            value=(i << 12) | (j << 8) | (k << 4))
        yield
        for i in range(1 << w.channel):
            for j in range(1 << w.profile):
                for k, l in enumerate("cfg a1 b0 b1".split()):
                    yield from dut.set_coeff(i, profile=j, coeff=l,
                            value=(i << 12) | (j << 8) | (k << 4))
                yield from dut.set_coeff(i, profile=j, coeff="cfg",
                        value=(i << 0) | (j << 8))  # sel, dly
        yield
        for i in range(10):
            yield from dut.check_iter()
            yield

    dut = iir.IIR(w)
    run_simulation(dut, [run(dut)], vcd_name="iir.vcd")


class IIRTest(unittest.TestCase):
    def test_run(self):
        main()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
