from collections import namedtuple

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
                accu=48, shift=11, profile=5, dly=8)
        dds_p = servo.DDSParams(width=8 + 32 + 16 + 16,
                channels=adc_p.channels, clk=1)

        self.timing = servo.predict_timing(adc_p, iir_p, dds_p)

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
    
    def test_phase_track(self):
        # This test only checks the phase accumulator
        # Parameters of ADC, IIR, and other interfaces do not matter
        # They only need to not obstruct the servo operations
        adc = 0
        channel = 3
        main_profile = 0
        alt_profile = 1

        def test_iterations():
            yield self.iir.ctrl[channel].en_iir.eq(1)
            yield self.iir.ctrl[channel].en_out.eq(1)
            yield self.iir.ctrl[channel].en_pt.eq(1)
            yield self.iir.ctrl[channel].profile.eq(main_profile)

            Profile = namedtuple('Profile', ['ftw', 'pow', 'fiducial_ts'])
            profiles = [Profile(ftw=0x28F5C29, pow=0x8000, fiducial_ts=0x1234), Profile(ftw=0xadbeef, pow=0, fiducial_ts=0x4321)]
            coeffs = [ dict(pow=p.pow, offset=0, ftw0=(p.ftw & 0xffff), ftw1=(p.ftw >> 16),
                    a1=0, b0=0, b1=0, cfg=adc | (0 << 3)) for p in profiles ]
            for ks in "pow offset ftw0 ftw1", "a1 b0 b1 cfg":
                for profile_i, coeff in enumerate(coeffs):
                    for k in ks.split():
                        yield from self.iir.set_coeff(channel, value=coeff[k],
                                profile=profile_i, coeff=k)
                yield
            for i, profile in enumerate(profiles):
                yield from self.iir.set_fiducial_timestamp(channel, i, profile.fiducial_ts)


            phase_accu = 0      # Assume phase accumulator is cleared
            # First processing time stamp is the ADC processing time
            t_elapsed = self.timing[0] * self.iir.sysclks_per_clk
            t_update = self.iir.t_cycle * self.iir.sysclks_per_clk

            duration = 10
            # time offset that profiles are toggled
            profile_applied = [ 1 if i >= 1 else 0 for i in range(duration) ]
            # Applied profile needs 2 IO_UPDATE cycles to go through the pipeline
            profile_processed = [0, 0] + profile_applied[:-2]

            yield self.start.eq(1)
            for iteration, profile_out in enumerate(profile_processed):
                while not (yield self.dds_tb.io_update):
                    yield
                # HACK: According to the simulation of THIS TESTBENCH,
                # iir_processing is always false during the IO_UPDATE pulse
                assert (yield self.iir.processing) == 0
                yield self.iir.ctrl[channel].profile.eq(profile_applied[iteration])
                yield  # io_update

                fiducial_ts = yield from self.iir.get_fiducial_timestamp(channel, profile_out)

                # DDS TB records are updated after the IO_UPDATE pulse
                ftw = yield self.dds_tb.ddss[channel].ftw
                pow_ = yield self.dds_tb.ddss[channel].pow
                expected_phase = ftw * (t_elapsed - fiducial_ts) + (profiles[profile_out].pow << 16)
                adjusted_phase = expected_phase - phase_accu
                adjusted_pow = (adjusted_phase >> 16) & 0xffff
                assert pow_ == adjusted_pow
                # Expected phase accumulator value by the next IO_UPDATE
                phase_accu += ftw * t_update
                phase_accu &= 0xffffffff
                t_elapsed += t_update

        yield from test_iterations()
        
        # test reset
        # disable the servo, and drain the pipeline
        yield self.start.eq(0)
        for _ in range(3*self.iir.t_cycle):
            yield

        # reset tracked values
        yield from self.iir.set_prev_ftw(channel, 0)
        yield from self.iir.set_phase_accumulator(channel, 0)

        yield from test_iterations()


def main(test_func_name="test"):
    servo = ServoSim()
    test_func = getattr(servo, test_func_name)
    run_simulation(servo, test_func(), vcd_name="servo_{}.vcd".format(test_func_name),
            clocks={
                "sys":   (8, 0),
                "adc":   (8, 0),
                "ret":   (8, 0),
                "async_": (2, 0),
            })


class ServoTest(unittest.TestCase):
    def test_run(self):
        main()


class PhaseTrackTest(unittest.TestCase):
    def test_run(self):
        main("test_phase_track")


if __name__ == "__main__":
    main()
