import logging
import unittest

from migen import *
from migen.genlib import io

from artiq.gateware.test.suservo import test_adc, test_dds
from artiq.gateware.suservo import servo


class ServoSim(servo.Servo):
    def __init__(self):
        adc_p = servo.ADCParams(width=16, channels=8, lanes=4,
                t_cnvh=4, t_conv=57 - 4, t_rtt=4 + 4)
        iir_p = servo.IIRWidths(state=25, coeff=18, adc=16, asf=14, word=16,
                accu=48, shift=11, channel=3, profile=5, dly=8)
        dds_p = servo.DDSParams(width=8 + 32 + 16 + 16,
                channels=adc_p.channels, clk=1)

        self.submodules.adc_tb = test_adc.TB(adc_p)
        self.submodules.dds_tb = test_dds.TB(dds_p)

        servo.Servo.__init__(self, self.adc_tb, self.dds_tb,
                adc_p, iir_p, dds_p)

    def test(self):
        assert (yield self.done)

        adc = 1
        x0 = 0x0141
        yield self.adc_tb.data[-adc-1].eq(x0)
        channel = 3
        yield self.iir.adc[channel].eq(adc)
        yield self.iir.ctrl[channel].en_iir.eq(1)
        yield self.iir.ctrl[channel].en_out.eq(1)
        profile = 5
        yield self.iir.ctrl[channel].profile.eq(profile)
        x1 = 0x0743
        yield from self.iir.set_state(adc, x1, coeff="x1")
        y1 = 0x1145
        yield from self.iir.set_state(channel, y1,
                profile=profile, coeff="y1")
        coeff = dict(pow=0x1333, offset=0x1531, ftw0=0x1727, ftw1=0x1929,
                a1=0x0135, b0=0x0337, b1=0x0539, cfg=adc | (0 << 3))
        for ks in "pow offset ftw0 ftw1", "a1 b0 b1 cfg":
            for k in ks.split():
                yield from self.iir.set_coeff(channel, value=coeff[k],
                        profile=profile, coeff=k)
            yield

        yield self.start.eq(1)
        yield
        yield self.start.eq(0)
        while not (yield self.dds_tb.io_update):
            yield
        yield  # io_update

        w = self.iir.widths

        x0 = x0 << (w.state - w.adc - 1)
        _ = yield from self.iir.get_state(adc, coeff="x1")
        assert _ == x0, (hex(_), hex(x0))

        offset = coeff["offset"] << (w.state - w.coeff - 1)
        a1, b0, b1 = coeff["a1"], coeff["b0"], coeff["b1"]
        out = (
                0*(1 << w.shift - 1) +  # rounding
                a1*(y1 + 0) + b0*(x0 + offset) + b1*(x1 + offset)
        ) >> w.shift
        y1 = min(max(0, out), (1 << w.state - 1) - 1)

        _ = yield from self.iir.get_state(channel, profile, coeff="y1")
        assert _ == y1, (hex(_), hex(y1))

        _ = yield self.dds_tb.ddss[channel].ftw
        ftw = (coeff["ftw1"] << 16) | coeff["ftw0"]
        assert _ == ftw, (hex(_), hex(ftw))

        _ = yield self.dds_tb.ddss[channel].pow
        assert _ == coeff["pow"], (hex(_), hex(coeff["pow"]))

        _ = yield self.dds_tb.ddss[channel].asf
        asf = y1 >> (w.state - w.asf - 1)
        assert _ == asf, (hex(_), hex(asf))


def main():
    servo = ServoSim()
    run_simulation(servo, servo.test(), vcd_name="servo.vcd",
            clocks={
                "sys":   (8, 0),
                "adc":   (8, 0),
                "ret":   (8, 0),
                "async": (2, 0),
            })


class ServoTest(unittest.TestCase):
    def test_run(self):
        main()


if __name__ == "__main__":
    main()
