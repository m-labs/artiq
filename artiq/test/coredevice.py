from math import sqrt

from artiq.language import *
from artiq.test.hardware_testbench import ExperimentCase
from artiq.coredevice.runtime_exceptions import RTIOUnderflow
from artiq.coredevice import runtime_exceptions


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
            # make sure not to send two commands into the same RTIO
            # channel with the same timestamp
            self.ttl_inout.gate_rising(5*us)
            with sequential:
                delay(1*us)
                t0 = now_mu()
                self.ttl_inout.pulse(1*us)
        self.rtt = mu_to_seconds(self.ttl_inout.timestamp() - t0)


class Loopback(Experiment, AutoDB):
    class DBKeys:
        core = Device()
        loop_in = Device()
        loop_out = Device()
        rtt = Result()

    @kernel
    def run(self):
        self.loop_in.input()
        delay(1*us)
        with parallel:
            self.loop_in.gate_rising(2*us)
            with sequential:
                delay(1*us)
                t0 = now_mu()
                self.loop_out.pulse(1*us)
        self.rtt = mu_to_seconds(self.loop_in.timestamp() - t0)


class ClockGeneratorLoopback(Experiment, AutoDB):
    class DBKeys:
        core = Device()
        loop_clock_in = Device()
        loop_clock_out = Device()
        count = Result()

    @kernel
    def run(self):
        self.loop_clock_in.input()
        self.loop_clock_out.stop()
        delay(1*us)
        with parallel:
            self.loop_clock_in.gate_rising(10*us)
            with sequential:
                delay(200*ns)
                self.loop_clock_out.set(1*MHz)
        self.count = self.loop_clock_in.count()


class PulseRate(Experiment, AutoDB):
    class DBKeys:
        core = Device()
        loop_out = Device()
        pulse_rate = Result()

    @kernel
    def run(self):
        dt = seconds_to_mu(1000*ns)
        while True:
            try:
                for i in range(1000):
                    self.loop_out.pulse_mu(dt)
                    delay_mu(dt)
            except RTIOUnderflow:
                dt += 1
                self.core.break_realtime()
            else:
                self.pulse_rate = mu_to_seconds(2*dt)
                break


class Watchdog(Experiment, AutoDB):
    class DBKeys:
        core = Device()

    @kernel
    def run(self):
        with watchdog(50*ms):
            while True:
                pass


class LoopbackCount(Experiment, AutoDB):
    class DBKeys:
        core = Device()
        ttl_inout = Device()
        npulses = Argument()

    def report(self, n):
        self.result = n

    @kernel
    def run(self):
        self.ttl_inout.output()
        delay(1*us)
        with parallel:
            self.ttl_inout.gate_rising(10*us)
            with sequential:
                for i in range(self.npulses):
                    delay(25*ns)
                    self.ttl_inout.pulse(25*ns)
        self.report(self.ttl_inout.count())


class Underflow(Experiment, AutoDB):
    class DBKeys:
        core = Device()
        ttl_out = Device()

    @kernel
    def run(self):
        while True:
            delay(25*ns)
            self.ttl_out.pulse(25*ns)


class SequenceError(Experiment, AutoDB):
    class DBKeys:
        core = Device()
        ttl_out = Device()

    @kernel
    def run(self):
        t = now_mu()
        self.ttl_out.pulse(25*us)
        at_mu(t)
        self.ttl_out.pulse(25*us)


class CoredeviceTest(ExperimentCase):
    def test_rtt(self):
        self.execute(RTT)
        rtt = self.dbh.get_result("rtt").read
        print(rtt)
        self.assertGreater(rtt, 0*ns)
        self.assertLess(rtt, 100*ns)

    def test_loopback(self):
        self.execute(Loopback)
        rtt = self.dbh.get_result("rtt").read
        print(rtt)
        self.assertGreater(rtt, 0*ns)
        self.assertLess(rtt, 50*ns)

    def test_clock_generator_loopback(self):
        self.execute(ClockGeneratorLoopback)
        count = self.dbh.get_result("count").read
        self.assertEqual(count, 10)

    def test_pulse_rate(self):
        self.execute(PulseRate)
        rate = self.dbh.get_result("pulse_rate").read
        print(rate)
        self.assertGreater(rate, 100*ns)
        self.assertLess(rate, 2500*ns)

    def test_loopback_count(self):
        npulses = 2
        r = self.execute(LoopbackCount, npulses=npulses)
        self.assertEqual(r.result, npulses)

    def test_underflow(self):
        with self.assertRaises(runtime_exceptions.RTIOUnderflow):
            self.execute(Underflow)

    def test_sequence_error(self):
        with self.assertRaises(runtime_exceptions.RTIOSequenceError):
            self.execute(SequenceError)

    def test_watchdog(self):
        # watchdog only works on the device
        with self.assertRaises(IOError):
            self.execute(Watchdog)


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
            t1 = self.core.get_rtio_counter_mu()
            self.nop(1)
            t2 = self.core.get_rtio_counter_mu()
            self.ts[i] = mu_to_seconds(t2 - t1)

    def run(self):
        self.bench()
        mean = sum(self.ts)/self.repeats
        self.rpc_time_stddev = sqrt(
            sum([(t - mean)**2 for t in self.ts])/self.repeats)*s
        self.rpc_time_mean = mean*s


class RPCTest(ExperimentCase):
    def test_rpc_timing(self):
        self.execute(RPCTiming)
        self.assertGreater(self.dbh.get_result("rpc_time_mean").read, 100*ns)
        self.assertLess(self.dbh.get_result("rpc_time_mean").read, 15*ms)
        self.assertLess(self.dbh.get_result("rpc_time_stddev").read, 1*ms)
