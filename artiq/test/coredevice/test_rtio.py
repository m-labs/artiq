# Copyright (C) 2014, 2015 M-Labs Limited
# Copyright (C) 2014, 2015 Robert Jordens <jordens@gmail.com>

import os, unittest
import numpy as np

from math import sqrt

from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase
from artiq.coredevice import exceptions
from artiq.coredevice.comm_mgmt import CommMgmt
from artiq.coredevice.comm_analyzer import (StoppedMessage, OutputMessage, InputMessage,
                                            decode_dump, get_analyzer_dump)


artiq_low_latency = os.getenv("ARTIQ_LOW_LATENCY")
artiq_in_devel = os.getenv("ARTIQ_IN_DEVEL")


class RTIOCounter(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    @kernel
    def run(self):
        t0 = self.core.get_rtio_counter_mu()
        t1 = self.core.get_rtio_counter_mu()
        self.set_dataset("dt", self.core.mu_to_seconds(t1 - t0))


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
        delay(20*us)
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
        self.setattr_device("dds0")
        self.setattr_device("dds1")

    @kernel
    def run(self):
        self.core.reset()
        dt = self.core.seconds_to_mu(5*us)
        freq = self.dds0.frequency_to_ftw(100*MHz)
        while True:
            delay(10*ms)
            for i in range(1250):
                try:
                    delay_mu(-self.dds0.set_duration_mu)
                    self.dds0.set_mu(freq)
                    delay_mu(self.dds0.set_duration_mu)
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
        delay(55*256*us)
        for _ in range(256):
            self.ttl_out.pulse(25*us)
            delay(-75*us)


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
        while self.core.get_rtio_counter_mu() < now_mu():
            pass


class AddressCollision(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("loop_in")

    @kernel
    def run(self):
        self.core.reset()
        self.loop_in.input()
        self.loop_in.pulse(10*us)
        while self.core.get_rtio_counter_mu() < now_mu():
            pass


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


class Rounding(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    @kernel
    def run(self):
        self.core.reset()
        t1 = now_mu()
        delay(8*us)
        t2 = now_mu()
        self.set_dataset("delta", t2 - t1)


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
    def test_rtio_counter(self):
        self.execute(RTIOCounter)
        dt = self.dataset_mgr.get("dt")
        print(dt)
        self.assertGreater(dt, 50*ns)
        self.assertLess(dt, 1*us)

    def test_loopback(self):
        self.execute(Loopback)
        rtt = self.dataset_mgr.get("rtt")
        print(rtt)
        self.assertGreater(rtt, 0*ns)
        self.assertLess(rtt, 140*ns)

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
        self.assertLess(rate, 16*us)

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

    def execute_and_test_in_log(self, experiment, string):
        core_addr = self.device_mgr.get_desc("core")["arguments"]["host"]
        mgmt = CommMgmt(core_addr)
        mgmt.clear_log()
        self.execute(experiment)
        log = mgmt.get_log()
        self.assertIn(string, log)
        mgmt.close()

    def test_sequence_error(self):
        self.execute_and_test_in_log(SequenceError, "RTIO sequence error")

    def test_collision(self):
        self.execute_and_test_in_log(Collision, "RTIO collision")

    def test_address_collision(self):
        self.execute_and_test_in_log(AddressCollision, "RTIO collision")

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

    def test_rounding(self):
        self.execute(Rounding)
        dt = self.dataset_mgr.get("delta")
        self.assertEqual(dt, 8000)


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
        self.assertLess(rpc_time_mean, 3.5*ms)
        self.assertLess(self.dataset_mgr.get("rpc_time_stddev"), 1*ms)


class _DMA(EnvExperiment):
    def build(self, trace_name="test_rtio"):
        self.setattr_device("core")
        self.setattr_device("core_dma")
        self.setattr_device("ttl1")
        self.trace_name = trace_name
        self.delta = np.int64(0)

    @kernel
    def record(self, for_handle=True):
        with self.core_dma.record(self.trace_name):
            # When not using the handle, retrieving the DMA trace
            # in dma.playback() can be slow. Allow some time.
            if not for_handle:
                delay(1*ms)
            delay(100*ns)
            self.ttl1.on()
            delay(100*ns)
            self.ttl1.off()

    @kernel
    def record_many(self, n):
        t1 = self.core.get_rtio_counter_mu()
        with self.core_dma.record(self.trace_name):
            for i in range(n//2):
                delay(100*ns)
                self.ttl1.on()
                delay(100*ns)
                self.ttl1.off()
        t2 = self.core.get_rtio_counter_mu()
        self.set_dataset("dma_record_time", self.core.mu_to_seconds(t2 - t1))

    @kernel
    def playback(self, use_handle=True):
        if use_handle:
            handle = self.core_dma.get_handle(self.trace_name)
            self.core.break_realtime()
            start = now_mu()
            self.core_dma.playback_handle(handle)
        else:
            self.core.break_realtime()
            start = now_mu()
            self.core_dma.playback(self.trace_name)
        self.delta = now_mu() - start

    @kernel
    def playback_many(self, n):
        handle = self.core_dma.get_handle(self.trace_name)
        self.core.break_realtime()
        t1 = self.core.get_rtio_counter_mu()
        for i in range(n):
            self.core_dma.playback_handle(handle)
        t2 = self.core.get_rtio_counter_mu()
        self.set_dataset("dma_playback_time", self.core.mu_to_seconds(t2 - t1))

    @kernel
    def erase(self):
        self.core_dma.erase(self.trace_name)

    @kernel
    def nested(self):
        with self.core_dma.record(self.trace_name):
            with self.core_dma.record(self.trace_name):
                pass

    @kernel
    def invalidate(self, mode):
        self.record()
        handle = self.core_dma.get_handle(self.trace_name)
        if mode == 0:
            self.record()
        elif mode == 1:
            self.erase()
        self.core_dma.playback_handle(handle)


class DMATest(ExperimentCase):
    def test_dma_storage(self):
        exp = self.create(_DMA)
        exp.record()
        exp.record() # overwrite
        exp.playback()
        exp.erase()
        with self.assertRaises(exceptions.DMAError):
            exp.playback()

    def test_dma_nested(self):
        exp = self.create(_DMA)
        with self.assertRaises(exceptions.DMAError):
            exp.nested()

    def test_dma_trace(self):
        core_host = self.device_mgr.get_desc("core")["arguments"]["host"]

        exp = self.create(_DMA)

        for use_handle in [False, True]:
            exp.record(use_handle)
            get_analyzer_dump(core_host)  # clear analyzer buffer
            exp.playback(use_handle)

            dump = decode_dump(get_analyzer_dump(core_host))
            self.assertEqual(len(dump.messages), 3)
            self.assertIsInstance(dump.messages[-1], StoppedMessage)
            self.assertIsInstance(dump.messages[0], OutputMessage)
            self.assertEqual(dump.messages[0].channel, 1)
            self.assertEqual(dump.messages[0].address, 0)
            self.assertEqual(dump.messages[0].data, 1)
            self.assertIsInstance(dump.messages[1], OutputMessage)
            self.assertEqual(dump.messages[1].channel, 1)
            self.assertEqual(dump.messages[1].address, 0)
            self.assertEqual(dump.messages[1].data, 0)
            self.assertEqual(dump.messages[1].timestamp -
                             dump.messages[0].timestamp, 100)

    def test_dma_delta(self):
        exp = self.create(_DMA)
        exp.record()

        exp.record(False)
        exp.playback(False)
        self.assertEqual(exp.delta, 1000200)

        exp.record(True)
        exp.playback(True)
        self.assertEqual(exp.delta, 200)

    def test_dma_record_time(self):
        exp = self.create(_DMA)
        count = 20000
        exp.record_many(count)
        dt = self.dataset_mgr.get("dma_record_time")
        print("dt={}, dt/count={}".format(dt, dt/count))
        self.assertLess(dt/count, 20*us)

    def test_dma_playback_time(self):
        exp = self.create(_DMA)
        count = 20000
        exp.record_many(40)
        exp.playback_many(count)
        dt = self.dataset_mgr.get("dma_playback_time")
        print("dt={}, dt/count={}".format(dt, dt/count))
        self.assertLess(dt/count, 4.5*us)

    def test_dma_underflow(self):
        exp = self.create(_DMA)
        exp.record()
        with self.assertRaises(RTIOUnderflow):
            exp.playback_many(20000)

    def test_handle_invalidation(self):
        exp = self.create(_DMA)
        for mode in [0, 1]:
            with self.assertRaises(exceptions.DMAError):
                exp.invalidate(mode)
