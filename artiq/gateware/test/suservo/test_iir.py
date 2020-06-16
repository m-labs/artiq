import logging
import unittest

from migen import *
from artiq.gateware.suservo import servo
from collections import namedtuple

logger = logging.getLogger(__name__)

ADCParamsSim = namedtuple("ADCParams", ["channels"])
DDSParamsSim = namedtuple("ADCParams", ["channels", "sysclk_per_clk"])

def main():
    w_kasli = servo.IIRWidths(state=25, coeff=18, adc=16, asf=14, 
            word=16, accu=48, shift=11, profile=5, dly=8)
    p_adc = ADCParamsSim(channels=8)
    p_dds = DDSParamsSim(channels=4, sysclk_per_clk=8)
    w = servo.IIRWidths(state=17, coeff=16, adc=16, asf=14,
            word=16, accu=48, shift=11, profile=2, dly=8)

    t_iir = p_adc.channels + 4*p_dds.channels + 8 + 1
    def run(dut):
        yield dut.t_running.eq(0)
        for i, ch in enumerate(dut.adc):
            yield ch.eq(i)
        for i, ch in enumerate(dut.ctrl):
            yield ch.en_iir.eq(1)
            yield ch.en_out.eq(1)
            yield ch.profile.eq(i)
            yield ch.en_pt.eq(i)
        for i, ch in enumerate(dut.ctrl_reftime):
            yield ch.sysclks_fine.eq(i)
            yield ch.stb.eq(1)
            yield
            yield dut.t_running.eq(dut.t_running + 1)
            yield ch.stb.eq(0)
            yield
            yield dut.t_running.eq(dut.t_running + 1)
        for i in range(p_adc.channels):
            yield from dut.set_state(i, i << 8, coeff="x1")
            yield from dut.set_state(i, i << 8, coeff="x0")
        for i in range(p_dds.channels):
            for j in range(1 << w.profile):
                yield from dut.set_state(i,
                        (j << 1) | (i << 8), profile=j, coeff="y1")
                for k, l in enumerate("pow offset ftw0 ftw1".split()):
                    yield from dut.set_coeff(i, profile=j, coeff=l,
                            value=(i << 10) | (j << 8) | (k << 4))
        yield
        for i in range(p_dds.channels):
            for j in range(1 << w.profile):
                for k, l in enumerate("a1 b0 b1".split()):
                    yield from dut.set_coeff(i, profile=j, coeff=l,
                            value=(i << 10) | (j << 8) | (k << 4))
                yield from dut.set_coeff(i, profile=j, coeff="cfg",
                        value=(i % p_adc.channels) | (j << 8))  # sel, dly
        yield
        for i in range(4):
            logger.debug("check_iter {}".format(i))
            yield from dut.check_iter()
            yield dut.t_running.eq((yield dut.t_running) + t_iir)
            yield

    dut = servo.IIR(w, p_adc, p_dds, t_iir)
    run_simulation(dut, [run(dut)], vcd_name="servo.vcd")


class IIRTest(unittest.TestCase):
    def test_run(self):
        main()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
