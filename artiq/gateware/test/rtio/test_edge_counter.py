import unittest

from migen import *
from artiq.gateware.rtio.phy.edge_counter import *

CONFIG_COUNT_RISING = 0b0001
CONFIG_COUNT_FALLING = 0b0010
CONFIG_SEND_COUNT_EVENT = 0b0100
CONFIG_RESET_TO_ZERO = 0b1000


class TimeoutError(Exception):
    pass


class Testbench:
    def __init__(self, counter_width=32):
        self.input = Signal()
        self.dut = SimpleEdgeCounter(self.input, counter_width=counter_width)

        self.fragment = self.dut.get_fragment()
        cd = ClockDomain("rio")
        self.fragment.clock_domains.append(cd)
        self.rio_rst = cd.rst

    def write_config(self, config):
        bus = self.dut.rtlink.o
        yield bus.data.eq(config)
        yield bus.stb.eq(1)
        yield
        yield bus.stb.eq(0)
        yield

    def read_event(self, timeout):
        bus = self.dut.rtlink.i
        for _ in range(timeout):
            if (yield bus.stb):
                break
            yield
        else:
            raise TimeoutError
        return (yield bus.data)

    def fetch_count(self, zero=False):
        c = CONFIG_SEND_COUNT_EVENT
        if zero:
            c |= CONFIG_RESET_TO_ZERO
        yield from self.write_config(c)
        return (yield from self.read_event(1))

    def toggle_input(self):
        yield self.input.eq(1)
        yield
        yield self.input.eq(0)
        yield

    def reset_rio(self):
        yield self.rio_rst.eq(1)
        yield
        yield self.rio_rst.eq(0)
        yield

    def run(self, gen):
        run_simulation(self.fragment, gen,
            clocks={n: 5 for n in ["sys", "rio", "rio_phy"]})


class TestEdgeCounter(unittest.TestCase):
    def test_init(self):
        tb = Testbench()

        def gen():
            # No counts initially...
            self.assertEqual((yield from tb.fetch_count()), 0)

            # ...nor any sensitivity.
            yield from tb.toggle_input()
            self.assertEqual((yield from tb.fetch_count()), 0)

        tb.run(gen())

    def test_sensitivity(self):
        tb = Testbench()

        def gen(sensitivity_config, expected_rising, expected_falling):
            yield from tb.write_config(sensitivity_config)
            yield tb.input.eq(1)
            yield
            self.assertEqual((yield from tb.fetch_count(zero=True)),
                             expected_rising)

            yield from tb.write_config(sensitivity_config)
            yield tb.input.eq(0)
            yield
            self.assertEqual((yield from tb.fetch_count()), expected_falling)

            yield
            with self.assertRaises(TimeoutError):
                # Make sure there are no more suprious events.
                yield from tb.read_event(10)

        tb.run(gen(CONFIG_COUNT_RISING, 1, 0))
        tb.run(gen(CONFIG_COUNT_FALLING, 0, 1))
        tb.run(gen(CONFIG_COUNT_RISING | CONFIG_COUNT_FALLING, 1, 1))

    def test_reset(self):
        tb = Testbench()

        def gen():
            # Generate one count.
            yield from tb.write_config(CONFIG_COUNT_RISING)
            yield from tb.toggle_input()
            self.assertEqual((yield from tb.fetch_count()), 1)

            # Make sure it is gone after an RTIO reset, and the counter isn't
            # sensitive anymore.
            yield from tb.write_config(CONFIG_COUNT_RISING)
            yield from tb.reset_rio()
            yield from tb.toggle_input()
            self.assertEqual((yield from tb.fetch_count()), 0)

        tb.run(gen())

    def test_saturation(self):
        for width in range(3, 5):
            tb = Testbench(counter_width=width)

            def gen():
                yield from tb.write_config(CONFIG_COUNT_RISING)
                for _ in range(2**width + 1):
                    yield from tb.toggle_input()
                self.assertEqual((yield from tb.fetch_count()), 2**width - 1)

            tb.run(gen())
