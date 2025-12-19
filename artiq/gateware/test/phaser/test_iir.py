from migen import *

from artiq.gateware.phaser.servo import FirstOrderIIR

from collections import namedtuple
import unittest


class DUT(Module):
    def __init__(
        self,
        input_width,
        output_width,
        coeff_width,
        offset_width,
        fractional_width,
        n_profiles,
    ):
        self.submodules.iir = iir = FirstOrderIIR(
            input_width,
            output_width,
            coeff_width,
            offset_width,
            fractional_width,
            n_profiles,
        )

        self.sink, self.source = iir.sink, iir.source


class TestBench:
    def __init__(
        self,
        input_width,
        output_width,
        coeff_width,
        offset_width,
        fractional_width,
        n_profiles,
    ):
        self.dut = DUT(
            input_width,
            output_width,
            coeff_width,
            offset_width,
            fractional_width,
            n_profiles,
        )
        self.fragment = self.dut.get_fragment()

        self.coeff_limit = 1 << (coeff_width - 1)
        self.offset_limit = 1 << (offset_width - 1)

    def delay(self, cycles):
        for _ in range(cycles):
            yield

    def enable_iir(self, en):
        yield self.dut.iir.enable.eq(1 if en else 0)
        yield

    def set_active_profile(self, profile):
        yield self.dut.iir.profile_sel.eq(profile)
        yield

    def set_iir_cfg_mu(self, profile, offset, b0, a1, b1):
        for coeff in [b0, a1, b1]:
            assert self.coeff_limit > coeff >= -self.coeff_limit
        assert self.offset_limit > offset >= -self.offset_limit

        cfg = self.dut.iir.configs[profile]
        yield cfg.a1.eq(a1)
        yield cfg.b0.eq(b0)
        yield cfg.b1.eq(b1)
        yield cfg.offset.eq(offset)
        yield

    def set_input(self, data):
        yield self.dut.sink.data.eq(data)
        yield self.dut.sink.stb.eq(1)
        yield
        yield self.dut.sink.stb.eq(0)

    def get_output(self):
        yield self.dut.source.ack.eq(1)
        while (yield self.dut.source.stb) != 1:
            yield
        data = yield self.dut.iir.source.data
        yield self.dut.source.ack.eq(0)
        return data

    def run(self, gen):
        run_simulation(self.fragment, gen, clocks={"sys": 8}, vcd_name="testbench.vcd")


class TestFirstOrderIIR(unittest.TestCase):
    def test_run(self):
        n_ch = 1
        n_profile = 4 * n_ch
        coeff_width = 18
        offset_width = 16
        fractional_width = 11

        input_width = 16
        output_width = 16

        output_limit = 1 << (output_width - 1)

        tb = TestBench(
            input_width,
            output_width,
            coeff_width,
            offset_width,
            fractional_width,
            n_profile,
        )

        def normalize(coeff):
            return int(round(coeff * (1 << fractional_width)))

        def gen(profile, offset, b0, a1, b1, inputs):
            b0_mu, a1_mu, b1_mu = normalize(b0), normalize(a1), normalize(b1)
            # filter setup
            yield from tb.set_iir_cfg_mu(profile, offset, b0_mu, a1_mu, b1_mu)
            yield from tb.set_active_profile(profile)
            yield from tb.enable_iir(True)

            # initial condition
            x1, y1 = 0, 0
            for i, data in enumerate(inputs):
                yield from tb.set_input(data)
                y0 = yield from tb.get_output()

                # verify output data
                x0 = data
                expected_y0 = (
                    (x0 + offset) * b0_mu + y1 * a1_mu + (x1 + offset) * b1_mu
                ) >> fractional_width
                expected_y0 = max(-output_limit, min(expected_y0, output_limit - 1))
                self.assertEqual(y0, expected_y0)

                # prepare next cycle
                x1 = x0
                y1 = y0

        test_case = namedtuple(
            "test_case", ["profile", "offset", "b0", "a1", "b1", "inputs"]
        )
        cases = [
            # Feedforward test
            test_case(
                profile=1,
                offset=50,
                b0=2.5,
                a1=0,
                b1=2.5,
                inputs=[i for i in range(50)],
            ),
            # Feedback test
            test_case(
                profile=2,
                offset=0,
                b0=1,
                a1=10,
                b1=0,
                inputs=[i for i in range(50)],
            ),
            # Feedback & Feedforward test
            test_case(
                profile=3,
                offset=0,
                b0=2.5,
                a1=10,
                b1=2.5,
                inputs=[i for i in range(50)],
            ),
        ]
        for c in cases:
            tb.run(gen(c.profile, c.offset, c.b0, c.a1, c.b1, c.inputs))


if __name__ == "__main__":
    unittest.main()
