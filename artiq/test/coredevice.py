from artiq import *
from artiq.test.hardware_testbench import *
from artiq.coredevice.runtime_exceptions import RTIOUnderflow


class RTTTest(ExperimentCase):
    class RTT(Experiment, AutoDB):
        class DBKeys:
            core = Device()
            ttl_inout = Device()
            rtt = Result()

        @kernel
        def run(self):
            self.ttl_inout.output()
            delay(1*us)
            t0 = now()
            with parallel:
                self.ttl_inout.gate_falling(2*us)
                self.ttl_inout.pulse(1*us)
            self.rtt = self.ttl_inout.timestamp() - t0

    def test_rtt(self):
        rtt = self.execute(self.RTT)["rtt"]
        self.assertGreater(rtt, 0*ns)
        self.assertLess(rtt, 40*ns)


class PulseRateTest(ExperimentCase):
    class PulseRate(Experiment, AutoDB):
        class DBKeys:
            core = Device()
            loop_out = Device()
            pulse_rate = Result()

        @kernel
        def run(self):
            dt = time_to_cycles(1000*ns)
            while True:
                try:
                    for i in range(1000):
                        self.loop_out.pulse(cycles_to_time(dt))
                        delay(cycles_to_time(dt))
                except RTIOUnderflow:
                    dt += 1
                    self.core.break_realtime()
                else:
                    self.pulse_rate = cycles_to_time(2*dt)
                    break

    def test_rate(self):
        rate = self.execute(self.PulseRate)["pulse_rate"]
        self.assertGreater(rate, 100*ns)
        self.assertLess(rate, 2000*ns)


