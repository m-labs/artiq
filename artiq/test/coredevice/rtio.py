# Copyright (C) 2014, 2015 M-Labs Limited
# Copyright (C) 2014, 2015 Robert Jordens <jordens@gmail.com>

from math import sqrt

from artiq.language import *
from artiq.test.hardware_testbench import ExperimentCase
from artiq.coredevice.exceptions import (RTIOUnderflow, RTIOSequenceError,
                                         RTIOCollisionError)


class RTT(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_inout")

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
        self.set_dataset("rtt", mu_to_seconds(self.ttl_inout.timestamp_mu() - t0))


class Loopback(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("loop_in")
        self.setattr_device("loop_out")

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
        self.set_dataset("rtt", mu_to_seconds(self.loop_in.timestamp_mu() - t0))


class ClockGeneratorLoopback(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("loop_clock_in")
        self.setattr_device("loop_clock_out")

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
        self.set_dataset("count", self.loop_clock_in.count())


class PulseRate(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_out")

    @kernel
    def run(self):
        dt = seconds_to_mu(1000*ns)
        while True:
            try:
                for i in range(1000):
                    self.ttl_out.pulse_mu(dt)
                    delay_mu(dt)
            except RTIOUnderflow:
                dt += 1
                self.core.break_realtime()
            else:
                self.set_dataset("pulse_rate", mu_to_seconds(2*dt))
                break


class Watchdog(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    @kernel
    def run(self):
        with watchdog(50*ms):
            while True:
                pass


class LoopbackCount(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_inout")
        self.setattr_argument("npulses")

    def set_count(self, count):
        self.set_dataset("count", count)

    @kernel
    def run(self):
        self.ttl_inout.output()
        delay(5*us)
        with parallel:
            self.ttl_inout.gate_rising(10*us)
            with sequential:
                for i in range(self.npulses):
                    delay(25*ns)
                    self.ttl_inout.pulse(25*ns)
        self.set_dataset("count", self.ttl_inout.count())


class Underflow(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_out")

    @kernel
    def run(self):
        while True:
            delay(25*ns)
            self.ttl_out.pulse(25*ns)


class SequenceError(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_out")

    @kernel
    def run(self):
        t = now_mu()
        self.ttl_out.pulse(25*us)
        at_mu(t)
        self.ttl_out.pulse(25*us)


class CollisionError(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_out_serdes")

    @kernel
    def run(self):
        delay(5*ms)  # make sure we won't get underflow
        for i in range(16):
            self.ttl_out_serdes.pulse_mu(1)
            delay_mu(1)


class TimeKeepsRunning(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    @kernel
    def run(self):
        self.set_dataset("time_at_start", now_mu())


class Handover(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    @kernel
    def k(self, var):
        self.set_dataset(var, now_mu())
        delay_mu(1234)

    def run(self):
        self.k("t1")
        self.k("t2")


class CoredeviceTest(ExperimentCase):
    def test_rtt(self):
        self.execute(RTT)
        rtt = self.dataset_mgr.get("rtt")
        print(rtt)
        self.assertGreater(rtt, 0*ns)
        self.assertLess(rtt, 100*ns)

    def test_loopback(self):
        self.execute(Loopback)
        rtt = self.dataset_mgr.get("rtt")
        print(rtt)
        self.assertGreater(rtt, 0*ns)
        self.assertLess(rtt, 50*ns)

    def test_clock_generator_loopback(self):
        self.execute(ClockGeneratorLoopback)
        count = self.dataset_mgr.get("count")
        self.assertEqual(count, 10)

    def test_pulse_rate(self):
        self.execute(PulseRate)
        rate = self.dataset_mgr.get("pulse_rate")
        print(rate)
        self.assertGreater(rate, 100*ns)
        self.assertLess(rate, 2500*ns)

    def test_loopback_count(self):
        npulses = 2
        self.execute(LoopbackCount, npulses=npulses)
        count = self.dataset_mgr.get("count")
        self.assertEqual(count, npulses)

    def test_underflow(self):
        with self.assertRaises(RTIOUnderflow):
            self.execute(Underflow)

    def test_sequence_error(self):
        with self.assertRaises(RTIOSequenceError):
            self.execute(SequenceError)

    def test_collision_error(self):
        with self.assertRaises(RTIOCollisionError):
            self.execute(CollisionError)

    def test_watchdog(self):
        # watchdog only works on the device
        with self.assertRaises(IOError):
            self.execute(Watchdog)

    def test_time_keeps_running(self):
        self.execute(TimeKeepsRunning)
        t1 = self.dataset_mgr.get("time_at_start")
        self.execute(TimeKeepsRunning)
        t2 = self.dataset_mgr.get("time_at_start")
        dead_time = mu_to_seconds(t2 - t1, self.device_mgr.get("core"))
        print(dead_time)
        self.assertGreater(dead_time, 1*ms)
        self.assertLess(dead_time, 2500*ms)

    def test_handover(self):
        self.execute(Handover)
        self.assertEqual(self.dataset_mgr.get("t1") + 1234,
                         self.dataset_mgr.get("t2"))


class RPCTiming(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_argument("repeats", PYONValue(100))

    def nop(self):
        pass

    @kernel
    def bench(self):
        for i in range(self.repeats):
            t1 = self.core.get_rtio_counter_mu()
            self.nop()
            t2 = self.core.get_rtio_counter_mu()
            self.ts[i] = mu_to_seconds(t2 - t1)

    def run(self):
        self.ts = [0. for _ in range(self.repeats)]
        self.bench()
        mean = sum(self.ts)/self.repeats
        self.set_dataset("rpc_time_stddev", sqrt(
            sum([(t - mean)**2 for t in self.ts])/self.repeats))
        self.set_dataset("rpc_time_mean", mean)


class RPCTest(ExperimentCase):
    def test_rpc_timing(self):
        self.execute(RPCTiming)
        self.assertGreater(self.dataset_mgr.get("rpc_time_mean"), 100*ns)
        self.assertLess(self.dataset_mgr.get("rpc_time_mean"), 15*ms)
        self.assertLess(self.dataset_mgr.get("rpc_time_stddev"), 1*ms)
