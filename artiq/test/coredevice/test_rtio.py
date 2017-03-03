# Copyright (C) 2014, 2015 M-Labs Limited
# Copyright (C) 2014, 2015 Robert Jordens <jordens@gmail.com>

import os, unittest

from math import sqrt

from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase
from artiq.coredevice import exceptions


artiq_low_latency = os.getenv("ARTIQ_LOW_LATENCY")


class PulseNotReceived(Exception):
    pass


class RTT(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_inout")

    @kernel
    def run(self):
        self.core.reset()
        self.ttl_inout.output()
        delay(1*us)
        with interleave:
            # make sure not to send two commands into the same RTIO
            # channel with the same timestamp
            self.ttl_inout.gate_rising(5*us)
            with sequential:
                delay(1*us)
                t0 = now_mu()
                self.ttl_inout.pulse(1*us)
        t1 = self.ttl_inout.timestamp_mu()
        if t1 < 0:
            raise PulseNotReceived()
        self.set_dataset("rtt", self.core.mu_to_seconds(t1 - t0))


class Loopback(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("loop_in")
        self.setattr_device("loop_out")

    @kernel
    def run(self):
        self.core.reset()
        self.loop_in.input()
        self.loop_out.off()
        delay(1*us)
        with parallel:
            self.loop_in.gate_rising(2*us)
            with sequential:
                delay(1*us)
                t0 = now_mu()
                self.loop_out.pulse(1*us)
        t1 = self.loop_in.timestamp_mu()
        if t1 < 0:
            raise PulseNotReceived()
        self.set_dataset("rtt", self.core.mu_to_seconds(t1 - t0))


class ClockGeneratorLoopback(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("loop_clock_in")
        self.setattr_device("loop_clock_out")

    @kernel
    def run(self):
        self.core.reset()
        self.loop_clock_in.input()
        self.loop_clock_out.stop()
        delay(10*us)
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
        self.core.reset()
        dt = self.core.seconds_to_mu(300*ns)
        while True:
            for i in range(10000):
                try:
                    self.ttl_out.pulse_mu(dt)
                    delay_mu(dt)
                except RTIOUnderflow:
                    dt += 1
                    self.core.break_realtime()
                    break
            else:
                self.set_dataset("pulse_rate", self.core.mu_to_seconds(dt))
                return


class PulseRateDDS(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("core_dds")
        self.setattr_device("dds0")
        self.setattr_device("dds1")

    @kernel
    def run(self):
        self.core.reset()
        dt = self.core.seconds_to_mu(5*us)
        freq = self.core_dds.frequency_to_ftw(100*MHz)
        while True:
            delay(10*ms)
            for i in range(1250):
                try:
                    with self.core_dds.batch:
                        self.dds0.set_mu(freq)
                        self.dds1.set_mu(freq)
                    delay_mu(dt)
                except RTIOUnderflow:
                    dt += 100
                    self.core.break_realtime()
                    break
            else:
                self.set_dataset("pulse_rate", self.core.mu_to_seconds(dt//2))
                return


class Watchdog(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    @kernel
    def run(self):
        with watchdog(50*ms):
            while True:
                pass


class LoopbackCount(EnvExperiment):
    def build(self, npulses):
        self.setattr_device("core")
        self.setattr_device("loop_in")
        self.setattr_device("loop_out")
        self.npulses = npulses

    def set_count(self, count):
        self.set_dataset("count", count)

    @kernel
    def run(self):
        self.core.reset()
        self.loop_in.input()
        self.loop_out.output()
        delay(5*us)
        with parallel:
            self.loop_in.gate_rising(10*us)
            with sequential:
                for i in range(self.npulses):
                    delay(25*ns)
                    self.loop_out.pulse(25*ns)
        self.set_dataset("count", self.loop_in.count())


class IncorrectLevel(Exception):
    pass


class Level(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("loop_in")
        self.setattr_device("loop_out")

    @kernel
    def run(self):
        self.core.reset()
        self.loop_in.input()
        self.loop_out.output()
        delay(5*us)

        self.loop_out.off()
        delay(5*us)
        if self.loop_in.sample_get_nonrt():
            raise IncorrectLevel

        self.loop_out.on()
        delay(5*us)
        if not self.loop_in.sample_get_nonrt():
            raise IncorrectLevel


class Watch(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("loop_in")
        self.setattr_device("loop_out")

    @kernel
    def run(self):
        self.core.reset()
        self.loop_in.input()
        self.loop_out.output()
        delay(5*us)

        self.loop_out.off()
        delay(5*us)
        if not self.loop_in.watch_stay_off():
            raise IncorrectLevel
        delay(10*us)
        if not self.loop_in.watch_done():
            raise IncorrectLevel

        delay(10*us)
        if not self.loop_in.watch_stay_off():
            raise IncorrectLevel
        delay(3*us)
        self.loop_out.on()
        delay(10*us)
        if self.loop_in.watch_done():
            raise IncorrectLevel


class Underflow(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_out")

    @kernel
    def run(self):
        self.core.reset()
        while True:
            delay(25*ns)
            self.ttl_out.pulse(25*ns)


class SequenceError(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_out")

    @kernel
    def run(self):
        self.core.reset()
        t = now_mu()
        self.ttl_out.pulse(25*us)
        at_mu(t)
        self.ttl_out.pulse(25*us)


class Collision(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_out_serdes")

    @kernel
    def run(self):
        self.core.reset()
        delay(5*ms)  # make sure we won't get underflow
        for i in range(16):
            self.ttl_out_serdes.pulse_mu(1)
            delay_mu(1)


class AddressCollision(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("loop_in")

    @kernel
    def run(self):
        self.core.reset()
        self.loop_in.input()
        self.loop_in.pulse(10*us)


class TimeKeepsRunning(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    @kernel
    def run(self):
        self.core.reset()
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


class DummyException(Exception):
    pass


class HandoverException(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    @kernel
    def k(self, var):
        self.set_dataset(var, now_mu())
        delay_mu(1234)
        raise DummyException()

    def run(self):
        try:
            self.k("t1")
        except DummyException:
            pass
        try:
            self.k("t2")
        except DummyException:
            pass


class CoredeviceTest(ExperimentCase):
    def test_loopback(self):
        self.execute(Loopback)
        rtt = self.dataset_mgr.get("rtt")
        print(rtt)
        self.assertGreater(rtt, 0*ns)
        self.assertLess(rtt, 60*ns)

    @unittest.skip("fails on CI for unknown reasons")
    def test_clock_generator_loopback(self):
        self.execute(ClockGeneratorLoopback)
        count = self.dataset_mgr.get("count")
        self.assertEqual(count, 10)

    def test_pulse_rate(self):
        """Minimum interval for sustained TTL output switching"""
        self.execute(PulseRate)
        rate = self.dataset_mgr.get("pulse_rate")
        print(rate)
        self.assertGreater(rate, 100*ns)
        self.assertLess(rate, 700*ns)

    def test_pulse_rate_dds(self):
        """Minimum interval for sustained DDS frequency switching"""
        self.execute(PulseRateDDS)
        rate = self.dataset_mgr.get("pulse_rate")
        print(rate)
        self.assertGreater(rate, 1*us)
        self.assertLess(rate, 8*us)

    def test_loopback_count(self):
        npulses = 2
        self.execute(LoopbackCount, npulses=npulses)
        count = self.dataset_mgr.get("count")
        self.assertEqual(count, npulses)

    def test_level(self):
        self.execute(Level)

    def test_watch(self):
        self.execute(Watch)

    def test_underflow(self):
        with self.assertRaises(RTIOUnderflow):
            self.execute(Underflow)

    def test_sequence_error(self):
        with self.assertRaises(RTIOSequenceError):
            self.execute(SequenceError)

    def test_collision(self):
        with self.assertRaises(RTIOCollision):
            self.execute(Collision)

    def test_address_collision(self):
        with self.assertRaises(RTIOCollision):
            self.execute(AddressCollision)

    def test_watchdog(self):
        # watchdog only works on the device
        with self.assertRaises(exceptions.WatchdogExpired):
            self.execute(Watchdog)

    @unittest.skipUnless(artiq_low_latency,
                         "timings are dependent on CPU load and network conditions")
    def test_time_keeps_running(self):
        self.execute(TimeKeepsRunning)
        t1 = self.dataset_mgr.get("time_at_start")
        self.execute(TimeKeepsRunning)
        t2 = self.dataset_mgr.get("time_at_start")

        dead_time = self.device_mgr.get("core").mu_to_seconds(t2 - t1)
        print(dead_time)
        self.assertGreater(dead_time, 1*ms)
        self.assertLess(dead_time, 2500*ms)

    def test_handover(self):
        self.execute(Handover)
        self.assertEqual(self.dataset_mgr.get("t1") + 1234,
                         self.dataset_mgr.get("t2"))

    def test_handover_exception(self):
        self.execute(HandoverException)
        self.assertEqual(self.dataset_mgr.get("t1") + 1234,
                         self.dataset_mgr.get("t2"))



class RPCTiming(EnvExperiment):
    def build(self, repeats=100):
        self.setattr_device("core")
        self.repeats = repeats

    def nop(self):
        pass

    @kernel
    def bench(self):
        for i in range(self.repeats):
            t1 = self.core.get_rtio_counter_mu()
            self.nop()
            t2 = self.core.get_rtio_counter_mu()
            self.ts[i] = self.core.mu_to_seconds(t2 - t1)

    def run(self):
        self.ts = [0. for _ in range(self.repeats)]
        self.bench()
        mean = sum(self.ts)/self.repeats
        self.set_dataset("rpc_time_stddev", sqrt(
            sum([(t - mean)**2 for t in self.ts])/self.repeats))
        self.set_dataset("rpc_time_mean", mean)


class RPCTest(ExperimentCase):
    @unittest.skipUnless(artiq_low_latency,
                         "timings are dependent on CPU load and network conditions")
    def test_rpc_timing(self):
        self.execute(RPCTiming)
        rpc_time_mean = self.dataset_mgr.get("rpc_time_mean")
        print(rpc_time_mean)
        self.assertGreater(rpc_time_mean, 100*ns)
        self.assertLess(rpc_time_mean, 2*ms)
        self.assertLess(self.dataset_mgr.get("rpc_time_stddev"), 1*ms)


class _DMA(EnvExperiment):
    def build(self, trace_name="foobar"):
        self.setattr_device("core")
        self.setattr_device("core_dma")
        self.setattr_device("ttl0")
        self.trace_name = trace_name

    @kernel
    def record(self):
        with self.core_dma.record(self.trace_name):
            delay(100*ns)
            self.ttl0.on()
            delay(100*ns)
            self.ttl0.off()

    @kernel
    def replay(self):
        self.core_dma.replay(self.trace_name)

    @kernel
    def erase(self):
        self.core_dma.erase(self.trace_name)

    @kernel
    def nested(self):
        with self.core_dma.record(self.trace_name):
            with self.core_dma.record(self.trace_name):
                pass


class DMATest(ExperimentCase):
    def test_dma_storage(self):
        exp = self.create(_DMA)
        exp.record()
        exp.record() # overwrite
        exp.replay()
        exp.erase()
        with self.assertRaises(exceptions.DMAError):
            exp.replay()

    def test_dma_nested(self):
        exp = self.create(_DMA)
        with self.assertRaises(exceptions.DMAError):
            exp.nested()

    # TODO: check replay against analyzer
