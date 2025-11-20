import logging
import unittest

from migen import *
from artiq.gateware.suservo import iir


def main():
    param_kasli = {
        "w": iir.IIRWidths(state=25, coeff=18, adc=16,
            asf=14, word=16, accu=48, shift=11,
            profile=5, dly=8),
        "i_channels": 8,
        "o_channels": 8,
    }
    param = {
        "w": iir.IIRWidths(state=17, coeff=16, adc=16,
            asf=14, word=16, accu=48, shift=11,
            profile=1, dly=8),
        "i_channels": 4,
        "o_channels": 4,
    }

    def run(dut):
        yield dut.t_running.eq(0xdeadbeef)
        for i in range(dut.o_channels):
            ch_tag = i & ((1 << 16) - 1)
            yield from dut.set_fiducial_timestamp(i, i % 2, ((0xf100 | ch_tag) << 16) | ((ch_tag << 8) | 0xf1))
            yield from dut.set_prev_ftw(i, ((0xf200 | ch_tag) << 16) | (0xf200 | ch_tag))
            yield from dut.set_phase_accumulator(i, (0xf3 << 24) | (0xf3 << 16) | (0xf300 | ch_tag))
        for i, ch in enumerate(dut.adc):
            yield ch.eq(i)
        for i, ch in enumerate(dut.ctrl):
            yield ch.en_iir.eq(1)
            yield ch.en_out.eq(1)
            yield ch.en_pt.eq(1)
            yield ch.profile.eq(i)
        for i in range(dut.i_channels):
            yield from dut.set_state(i, i << 8, coeff="x1")
            yield from dut.set_state(i, i << 8, coeff="x0")
        for i in range(dut.o_channels):
            for j in range(1 << dut.widths.profile):
                yield from dut.set_state(i,
                        (j << 1) | (i << 8), profile=j, coeff="y1")
                for k, l in enumerate("pow offset ftw0 ftw1".split()):
                    yield from dut.set_coeff(i, profile=j, coeff=l,
                            value=(i << 12) | (j << 8) | (k << 4))
        yield
        for i in range(dut.o_channels):
            for j in range(1 << dut.widths.profile):
                for k, l in enumerate("cfg a1 b0 b1".split()):
                    yield from dut.set_coeff(i, profile=j, coeff=l,
                            value=(i << 12) | (j << 8) | (k << 4))
                yield from dut.set_coeff(i, profile=j, coeff="cfg",
                        value=(i << 0) | (j << 8))  # sel, dly
        yield
        for i in range(10):
            yield from dut.check_iter()
            yield

    # assume t_cycle == t_iir, see predict_timing() in servo.py
    servo_param = param
    servo_param["t_cycle"] = servo_param["i_channels"] + 4*servo_param["o_channels"] + 8 + 1

    dut = iir.IIR(**servo_param)
    run_simulation(dut, [run(dut)], vcd_name="iir.vcd")


class IIRTest(unittest.TestCase):
    def test_run(self):
        main()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
