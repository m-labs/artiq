from math import sqrt

from artiq.language import *
from artiq.test.hardware_testbench import ExperimentCase
from artiq.coredevice.runtime_exceptions import RTIOUnderflow


class RTT(Experiment, AutoDB):
    class DBKeys:
        core = Device()
        ttl_inout = Device()
        rtt = Result()

    @kernel
    def run(self):
        self.ttl_inout.output()
        delay(1*us)
        with parallel:
            self.ttl_inout.gate_rising(2*us)
            with sequential:
                delay(1*us)
                t0 = now()
                self.ttl_inout.pulse(1*us)
        self.rtt = self.ttl_inout.timestamp() - t0


class Loopback(Experiment, AutoDB):
    class DBKeys:
        core = Device()
        loop_in = Device()
        loop_out = Device()
        rtt = Result()

    @kernel
    def run(self):
        with parallel:
            self.loop_in.gate_rising(2*us)
            with sequential:
                delay(1*us)
                t0 = now()
                self.loop_out.pulse(1*us)
        self.rtt = self.loop_in.timestamp() - t0


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


class CoredeviceTest(ExperimentCase):
    def test_rtt(self):
        rtt = self.execute(RTT)["rtt"]
        print(rtt)
        self.assertGreater(rtt, 0*ns)
        self.assertLess(rtt, 100*ns)

    def test_loopback(self):
        rtt = self.execute(Loopback)["rtt"]
        print(rtt)
        self.assertGreater(rtt, 0*ns)
        self.assertLess(rtt, 40*ns)

    def test_pulse_rate(self):
        rate = self.execute(PulseRate)["pulse_rate"]
        print(rate)
        self.assertGreater(rate, 100*ns)
        self.assertLess(rate, 2500*ns)


class RPCTiming(Experiment, AutoDB):
    class DBKeys:
        core = Device()
        repeats = Argument(100)
        rpc_time_mean = Result()
        rpc_time_stddev = Result()

    def nop(self, x):
        pass

    @kernel
    def bench(self):
        self.ts = [0. for _ in range(self.repeats)]
        for i in range(self.repeats):
            t1 = self.core.get_rtio_time()
            self.nop(1)
            t2 = self.core.get_rtio_time()
            self.ts[i] = t2 - t1

    def run(self):
        self.bench()
        mean = sum(self.ts)/self.repeats
        self.rpc_time_stddev = sqrt(
            sum([(t - mean)**2 for t in self.ts])/self.repeats)*s
        self.rpc_time_mean = mean*s


class RPCTest(ExperimentCase):
    def test_rpc_timing(self):
        res = self.execute(RPCTiming)
        print(res)
        self.assertGreater(res["rpc_time_mean"], 100*ns)
        self.assertLess(res["rpc_time_mean"], 10*ms)
        self.assertLess(res["rpc_time_stddev"], 1*ms)
