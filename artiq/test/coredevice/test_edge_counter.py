from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase


class EdgeCounterExp(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("loop_in_counter")
        self.setattr_device("loop_out")

    @kernel
    def count_pulse_edges(self, gate_fn):
        self.core.break_realtime()
        with parallel:
            with sequential:
                delay(5 * us)
                self.loop_out.pulse(10 * us)
            with sequential:
                gate_fn(10 * us)
                delay(1 * us)
                gate_fn(10 * us)
        return (self.loop_in_counter.fetch_count(),
                self.loop_in_counter.fetch_count())

    @kernel
    def timeout_timestamp(self):
        self.core.break_realtime()
        timestamp_mu, _ = self.loop_in_counter.fetch_timestamped_count(
            now_mu())
        return timestamp_mu

    @kernel
    def gate_relative_timestamp(self):
        self.core.break_realtime()
        gate_end_mu = self.loop_in_counter.gate_rising(1 * us)
        timestamp_mu, _ = self.loop_in_counter.fetch_timestamped_count()
        return timestamp_mu - gate_end_mu

    @kernel
    def many_pulses_split(self, num_pulses):
        self.core.break_realtime()

        self.loop_in_counter.set_config(
            count_rising=True,
            count_falling=True,
            send_count_event=False,
            reset_to_zero=True)

        for _ in range(num_pulses):
            self.loop_out.pulse(5 * us)
            delay(5 * us)

        self.loop_in_counter.set_config(
            count_rising=True,
            count_falling=True,
            send_count_event=True,
            reset_to_zero=False)

        for _ in range(num_pulses):
            self.loop_out.pulse(5 * us)
            delay(5 * us)

        self.loop_in_counter.set_config(
            count_rising=False,
            count_falling=False,
            send_count_event=True,
            reset_to_zero=False)

        return (self.loop_in_counter.fetch_count(),
                self.loop_in_counter.fetch_count())


class EdgeCounterTest(ExperimentCase):
    def setUp(self):
        super().setUp()
        self.exp = self.create(EdgeCounterExp)

    def test_sensitivity(self):
        c = self.exp.loop_in_counter
        self.assertEqual(self.exp.count_pulse_edges(c.gate_rising), (1, 0))
        self.assertEqual(self.exp.count_pulse_edges(c.gate_falling), (0, 1))
        self.assertEqual(self.exp.count_pulse_edges(c.gate_both), (1, 1))

    def test_timeout_timestamp(self):
        self.assertEqual(self.exp.timeout_timestamp(), -1)

    def test_gate_timestamp(self):
        # The input event should be received at some point after it was
        # requested, with some extra latency as it makes its way through the
        # DRTIO machinery. (We only impose a somewhat arbitrary upper limit
        # on the latency here.)
        delta_mu = self.exp.gate_relative_timestamp()
        self.assertGreaterEqual(delta_mu, 0)
        self.assertLess(delta_mu, 100)

    def test_many_pulses_split(self):
        self.assertEqual(self.exp.many_pulses_split(500), (1000, 2000))
