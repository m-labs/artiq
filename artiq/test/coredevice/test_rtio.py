# Copyright (C) 2014, 2015 M-Labs Limited
# Copyright (C) 2014, 2015 Robert Jordens <jordens@gmail.com>

import os, unittest
from numpy import int32, int64

from math import sqrt

from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase
from artiq.coredevice import exceptions
from artiq.coredevice.core import Core
from artiq.coredevice.dma import CoreDMA
from artiq.coredevice.ttl import TTLOut, TTLInOut, TTLClockGen
from artiq.coredevice.ad9914 import AD9914
from artiq.coredevice.comm_mgmt import CommMgmt
from artiq.coredevice.comm_analyzer import (StoppedMessage, OutputMessage, InputMessage,
                                            decode_dump, get_analyzer_dump)


artiq_low_latency = os.getenv("ARTIQ_LOW_LATENCY")


@nac3
class RTIOCounter(EnvExperiment):
    core: KernelInvariant[Core]

    def build(self):
        self.setattr_device("core")

    @rpc
    def report(self, dt: float):
        self.set_dataset("dt", dt)

    @kernel
    def run(self):
        t0 = self.core.get_rtio_counter_mu()
        t1 = self.core.get_rtio_counter_mu()
        self.report(self.core.mu_to_seconds(t1 - t0))


@nac3
class InvalidCounter(Exception):
    pass


@nac3
class WaitForRTIOCounter(EnvExperiment):
    core: KernelInvariant[Core]

    def build(self):
        self.setattr_device("core")

    @kernel
    def run(self):
        self.core.break_realtime()
        target_mu = now_mu() + int64(10000)
        self.core.wait_until_mu(target_mu)
        if self.core.get_rtio_counter_mu() < target_mu:
            raise InvalidCounter


@nac3
class PulseNotReceived(Exception):
    pass


@nac3
class RTT(EnvExperiment):
    core: KernelInvariant[Core]
    ttl_inout: KernelInvariant[TTLInOut]

    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_inout")

    @rpc
    def report(self, rtt: float):
        self.set_dataset("rtt", rtt)

    @kernel
    def run(self):
        self.core.reset()
        self.ttl_inout.output()
        self.core.delay(1.*us)
        t0 = int64(0)
        with parallel:
            # make sure not to send two commands into the same RTIO
            # channel with the same timestamp
            self.ttl_inout.gate_rising(5.*us)
            with sequential:
                self.core.delay(1.*us)
                t0 = now_mu()
                self.ttl_inout.pulse(1.*us)
        t1 = self.ttl_inout.timestamp_mu(now_mu())
        if t1 < int64(0):
            raise PulseNotReceived
        self.report(self.core.mu_to_seconds(t1 - t0))


@nac3
class Loopback(EnvExperiment):
    core: KernelInvariant[Core]
    loop_in: KernelInvariant[TTLInOut]
    loop_out: KernelInvariant[TTLOut]

    def build(self):
        self.setattr_device("core")
        self.setattr_device("loop_in")
        self.setattr_device("loop_out")

    @rpc
    def report(self, rtt: float):
        self.set_dataset("rtt", rtt)

    @kernel
    def run(self):
        self.core.reset()
        self.loop_in.input()
        self.loop_out.off()
        self.core.delay(1.*us)
        t0 = int64(0)
        with parallel:
            self.loop_in.gate_rising(2.*us)
            with sequential:
                self.core.delay(1.*us)
                t0 = now_mu()
                self.loop_out.pulse(1.*us)
        t1 = self.loop_in.timestamp_mu(now_mu())
        if t1 < int64(0):
            raise PulseNotReceived
        self.report(self.core.mu_to_seconds(t1 - t0))


@nac3
class ClockGeneratorLoopback(EnvExperiment):
    core: KernelInvariant[Core]
    loop_clock_in: KernelInvariant[TTLInOut]
    loop_clock_out: KernelInvariant[TTLClockGen]

    def build(self):
        self.setattr_device("core")
        self.setattr_device("loop_clock_in")
        self.setattr_device("loop_clock_out")

    @rpc
    def report(self, count: int32):
        self.set_dataset("count", count)

    @kernel
    def run(self):
        self.core.reset()
        self.loop_clock_in.input()
        self.loop_clock_out.stop()
        self.core.delay(200.*us)
        with parallel:
            self.loop_clock_in.gate_rising(10.*us)
            with sequential:
                self.core.delay(200.*ns)
                self.loop_clock_out.set(1.*MHz)
        self.report(self.loop_clock_in.count(now_mu()))


@nac3
class PulseRate(EnvExperiment):
    core: KernelInvariant[Core]
    ttl_out: KernelInvariant[TTLOut]

    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_out")

    @rpc
    def report(self, pulse_rate: float):
        self.set_dataset("pulse_rate", pulse_rate)

    @kernel
    def run(self):
        self.core.reset()
        dt = self.core.seconds_to_mu(300.*ns)
        i = 10000
        while i > 0:
            try:
                self.ttl_out.pulse_mu(dt)
                delay_mu(dt)
            except RTIOUnderflow:
                dt += int64(1)
                i = 10000
                self.core.break_realtime()
            else:
                i -= 1
        self.report(self.core.mu_to_seconds(dt))


@nac3
class PulseRateAD9914DDS(EnvExperiment):
    core: KernelInvariant[Core]
    ad9914dds0: KernelInvariant[AD9914]
    ad9914dds1: KernelInvariant[AD9914]

    def build(self):
        self.setattr_device("core")
        self.setattr_device("ad9914dds0")
        self.setattr_device("ad9914dds1")

    @rpc
    def report(self, pulse_rate: float):
        self.set_dataset("pulse_rate", pulse_rate)

    @kernel
    def run(self):
        self.core.reset()
        dt = self.core.seconds_to_mu(5.*us)
        freq = self.ad9914dds0.frequency_to_ftw(100.*MHz)
        while True:
            self.core.delay(10.*ms)
            for i in range(1250):
                try:
                    delay_mu(-self.ad9914dds0.set_duration_mu)
                    self.ad9914dds0.set_mu(freq)
                    delay_mu(self.ad9914dds0.set_duration_mu)
                    self.ad9914dds1.set_mu(freq)
                    delay_mu(dt)
                except RTIOUnderflow:
                    dt += int64(100)
                    self.core.break_realtime()
                    break
            else:
                self.report(self.core.mu_to_seconds(dt//int64(2)))
                return


@nac3
class LoopbackCount(EnvExperiment):
    core: KernelInvariant[Core]
    loop_in: KernelInvariant[TTLInOut]
    loop_out: KernelInvariant[TTLOut]
    npulses: KernelInvariant[int32]

    def build(self, npulses):
        self.setattr_device("core")
        self.setattr_device("loop_in")
        self.setattr_device("loop_out")
        self.npulses = npulses

    @rpc
    def report(self, count: int32):
        self.set_dataset("count", count)

    @kernel
    def run(self):
        self.core.reset()
        self.loop_in.input()
        self.loop_out.output()
        self.core.delay(5.*us)
        with parallel:
            self.loop_in.gate_rising(10.*us)
            with sequential:
                for i in range(self.npulses):
                    self.core.delay(25.*ns)
                    self.loop_out.pulse(25.*ns)
        self.report(self.loop_in.count(now_mu()))


@nac3
class IncorrectPulseTiming(Exception):
    pass


@nac3
class LoopbackGateTiming(EnvExperiment):
    core: KernelInvariant[Core]
    loop_in: KernelInvariant[TTLInOut]
    loop_out: KernelInvariant[TTLOut]

    def build(self):
        self.setattr_device("core")
        self.setattr_device("loop_in")
        self.setattr_device("loop_out")

    @kernel
    def run(self):
        # Make sure there are no leftover events.
        self.core.reset()
        self.loop_in.input()
        self.loop_out.output()
        delay_mu(int64(500))
        self.loop_out.off()
        delay_mu(int64(5000))

        # Determine loop delay.
        out_mu = int64(0)
        with parallel:
            self.loop_in.gate_rising_mu(int64(10000))
            with sequential:
                delay_mu(int64(5000))
                out_mu = now_mu()
                self.loop_out.pulse_mu(int64(1000))
        in_mu = self.loop_in.timestamp_mu(now_mu())
        if in_mu < int64(0):
            raise PulseNotReceived("Cannot determine loop delay")
        loop_delay_mu = in_mu - out_mu

        # With the exact delay known, make sure tight gate timings work.
        # In the most common configuration, 24 mu == 24 ns == 3 coarse periods,
        # which should be plenty of slack.
        # FIXME: ZC706 with NIST_QC2 needs 48ns - hw problem?
        delay_mu(int64(10000))

        gate_start_mu = now_mu()
        self.loop_in.gate_both_mu(int64(48)) # XXX
        gate_end_mu = now_mu()

        # gateware latency offset between gate and input
        lat_offset = int64(11*8)
        out_mu = gate_start_mu - loop_delay_mu + lat_offset
        at_mu(out_mu)
        self.loop_out.pulse_mu(int64(48)) # XXX

        in_mu = self.loop_in.timestamp_mu(gate_end_mu)
        print_rpc("timings:")
        print_rpc(gate_start_mu)
        print_rpc(in_mu - lat_offset)
        print_rpc(gate_end_mu)
        if in_mu < int64(0):
            raise PulseNotReceived
        if not (gate_start_mu <= (in_mu - lat_offset) <= gate_end_mu):
            raise IncorrectPulseTiming("Input event should occur during gate")
        if not (int64(-2) < (in_mu - out_mu - loop_delay_mu) < int64(2)):
            raise IncorrectPulseTiming("Loop delay should not change")

        in_mu = self.loop_in.timestamp_mu(gate_end_mu)
        if in_mu > int64(0):
            raise IncorrectPulseTiming("Only one pulse should be received")


@nac3
class IncorrectLevel(Exception):
    pass


@nac3
class Level(EnvExperiment):
    core: KernelInvariant[Core]
    loop_in: KernelInvariant[TTLInOut]
    loop_out: KernelInvariant[TTLOut]

    def build(self):
        self.setattr_device("core")
        self.setattr_device("loop_in")
        self.setattr_device("loop_out")

    @kernel
    def run(self):
        self.core.reset()
        self.loop_in.input()
        self.loop_out.output()
        self.core.delay(5.*us)

        self.loop_out.off()
        self.core.delay(5.*us)
        if self.loop_in.sample_get_nonrt() != 0:
            raise IncorrectLevel

        self.loop_out.on()
        self.core.delay(5.*us)
        if self.loop_in.sample_get_nonrt() == 0:
            raise IncorrectLevel


@nac3
class Watch(EnvExperiment):
    core: KernelInvariant[Core]
    loop_in: KernelInvariant[TTLInOut]
    loop_out: KernelInvariant[TTLOut]

    def build(self):
        self.setattr_device("core")
        self.setattr_device("loop_in")
        self.setattr_device("loop_out")

    @kernel
    def run(self):
        self.core.reset()
        self.loop_in.input()
        self.loop_out.output()
        self.core.delay(5.*us)

        self.loop_out.off()
        self.core.delay(5.*us)
        if not self.loop_in.watch_stay_off():
            raise IncorrectLevel
        self.core.delay(10.*us)
        if not self.loop_in.watch_done():
            raise IncorrectLevel

        self.core.delay(10.*us)
        if not self.loop_in.watch_stay_off():
            raise IncorrectLevel
        self.core.delay(3.*us)
        self.loop_out.on()
        self.core.delay(10.*us)
        if self.loop_in.watch_done():
            raise IncorrectLevel


@nac3
class Underflow(EnvExperiment):
    core: KernelInvariant[Core]
    ttl_out: KernelInvariant[TTLOut]

    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_out")

    @kernel
    def run(self):
        self.core.reset()
        while True:
            self.core.delay(25.*ns)
            self.ttl_out.pulse(25.*ns)


@nac3
class SequenceError(EnvExperiment):
    core: KernelInvariant[Core]
    ttl_out: KernelInvariant[TTLOut]

    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_out")

    @kernel
    def run(self):
        self.core.reset()
        self.core.delay(55.*256.*us)
        for _ in range(256):
            self.ttl_out.pulse(25.*us)
            self.core.delay(-75.*us)


@nac3
class Collision(EnvExperiment):
    core: KernelInvariant[Core]
    ttl_out_serdes: KernelInvariant[TTLOut]

    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_out_serdes")

    @kernel
    def run(self):
        self.core.reset()
        self.core.delay(5.*ms)  # make sure we won't get underflow
        for i in range(16):
            self.ttl_out_serdes.pulse_mu(int64(1))
            delay_mu(int64(1))
        while self.core.get_rtio_counter_mu() < now_mu():
            pass


@nac3
class AddressCollision(EnvExperiment):
    core: KernelInvariant[Core]
    loop_in: KernelInvariant[TTLInOut]

    def build(self):
        self.setattr_device("core")
        self.setattr_device("loop_in")

    @kernel
    def run(self):
        self.core.reset()
        self.loop_in.input()
        self.loop_in.pulse(10.*us)
        while self.core.get_rtio_counter_mu() < now_mu():
            pass


@nac3
class TimeKeepsRunning(EnvExperiment):
    core: KernelInvariant[Core]

    def build(self):
        self.setattr_device("core")

    @rpc
    def report(self, time_at_start: int64):
        self.set_dataset("time_at_start", time_at_start)

    @kernel
    def run(self):
        self.core.reset()
        self.report(now_mu())


@nac3
class Handover(EnvExperiment):
    core: KernelInvariant[Core]

    def build(self):
        self.setattr_device("core")

    @rpc
    def report(self, var: str, t: int64):
        self.set_dataset(var, t)

    @kernel
    def k(self, var: str):
        self.report(var, now_mu())
        delay_mu(int64(1234))

    def run(self):
        self.k("t1")
        self.k("t2")


@nac3
class Rounding(EnvExperiment):
    core: KernelInvariant[Core]

    def build(self):
        self.setattr_device("core")

    @rpc
    def report(self, delta: int64):
        self.set_dataset("delta", delta)

    @kernel
    def run(self):
        self.core.reset()
        t1 = now_mu()
        self.core.delay(8.*us)
        t2 = now_mu()
        self.report(t2 - t1)


@nac3
class DummyException(Exception):
    pass


@nac3
class HandoverException(EnvExperiment):
    core: KernelInvariant[Core]

    def build(self):
        self.setattr_device("core")

    @rpc
    def report(self, var: str, t: int64):
        self.set_dataset(var, t)

    @kernel
    def k(self, var: str):
        self.report(var, now_mu())
        delay_mu(int64(1234))
        raise DummyException

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

    def test_wait_for_rtio_counter(self):
        self.execute(WaitForRTIOCounter)

    def test_loopback(self):
        self.execute(Loopback)
        rtt = self.dataset_mgr.get("rtt")
        print(rtt)
        self.assertGreater(rtt, 20*ns)
        # on Kasli systems, this has to go through the isolated DIO card
        self.assertLess(rtt, 170*ns)

    def test_clock_generator_loopback(self):
        self.execute(ClockGeneratorLoopback)
        count = self.dataset_mgr.get("count")
        self.assertEqual(count, 10)

    @unittest.skip("NAC3TODO https://git.m-labs.hk/M-Labs/nac3/issues/532")
    def test_pulse_rate(self):
        """Minimum interval for sustained TTL output switching"""
        exp = self.execute(PulseRate)
        rate = self.dataset_mgr.get("pulse_rate")
        print(rate)
        self.assertGreater(rate, 100*ns)
        if exp.core.target == "cortexa9":
            # Crappy AXI PS/PL interface from Xilinx is slow.
            self.assertLess(rate, 810*ns)
        else:
            self.assertLess(rate, 480*ns)

    def test_pulse_rate_ad9914_dds(self):
        """Minimum interval for sustained AD9914 DDS frequency switching"""
        self.execute(PulseRateAD9914DDS)
        rate = self.dataset_mgr.get("pulse_rate")
        print(rate)
        self.assertGreater(rate, 1*us)
        self.assertLess(rate, 16*us)

    def test_loopback_count(self):
        npulses = 2
        self.execute(LoopbackCount, npulses=npulses)
        count = self.dataset_mgr.get("count")
        self.assertEqual(count, npulses)

    def test_loopback_gate_timing(self):
        self.execute(LoopbackGateTiming)

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
        try:
            mgmt.clear_log()
            self.execute(experiment)
            log = mgmt.get_log()
            self.assertIn(string, log)
        finally:
            mgmt.close()

    def test_sequence_error(self):
        self.execute_and_test_in_log(SequenceError, "RTIO sequence error")

    def test_collision(self):
        self.execute_and_test_in_log(Collision, "RTIO collision")

    def test_address_collision(self):
        self.execute_and_test_in_log(AddressCollision, "RTIO collision")

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


@nac3
class RPCTiming(EnvExperiment):
    core: KernelInvariant[Core]
    repeats: KernelInvariant[int32]
    ts: Kernel[list[float]]

    def build(self, repeats=100):
        self.setattr_device("core")
        self.repeats = repeats

    @rpc
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


@nac3
class _DMA(EnvExperiment):
    core: KernelInvariant[Core]
    core_dma: KernelInvariant[CoreDMA]
    ttl_out: KernelInvariant[TTLOut]
    trace_name: Kernel[str]
    delta: Kernel[int64]

    def build(self, trace_name="test_rtio"):
        self.setattr_device("core")
        self.setattr_device("core_dma")
        self.setattr_device("ttl_out")
        self.trace_name = trace_name
        self.delta = int64(0)

    @kernel
    def record(self, for_handle: bool = True):
        self.core_dma.prepare_record(self.trace_name)
        with self.core_dma.recorder:
            # When not using the handle, retrieving the DMA trace
            # in dma.playback() can be slow. Allow some time.
            if not for_handle:
                self.core.delay(1.*ms)
            self.core.delay(100.*ns)
            self.ttl_out.on()
            self.core.delay(100.*ns)
            self.ttl_out.off()

    @rpc
    def set_record_time(self, time: float):
        self.set_dataset("dma_record_time", time)

    @kernel
    def record_many(self, n: int32):
        t1 = self.core.get_rtio_counter_mu()
        self.core_dma.prepare_record(self.trace_name)
        with self.core_dma.recorder:
            for i in range(n//2):
                self.core.delay(100.*ns)
                self.ttl_out.on()
                self.core.delay(100.*ns)
                self.ttl_out.off()
        t2 = self.core.get_rtio_counter_mu()
        self.set_record_time(self.core.mu_to_seconds(t2 - t1))

    @kernel
    def playback(self, use_handle: bool = True):
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

    @rpc
    def set_playback_time(self, time: float):
        self.set_dataset("dma_playback_time", time)

    @kernel
    def playback_many(self, n: int32, add_delay: bool = False):
        handle = self.core_dma.get_handle(self.trace_name)
        self.core.break_realtime()
        t1 = self.core.get_rtio_counter_mu()
        for i in range(n):
            if add_delay:
                self.core.delay(2.*us)
            self.core_dma.playback_handle(handle)
        t2 = self.core.get_rtio_counter_mu()
        self.set_playback_time(self.core.mu_to_seconds(t2 - t1))

    @kernel
    def erase(self):
        self.core_dma.erase(self.trace_name)

    @kernel
    def nested(self):
        self.core_dma.prepare_record(self.trace_name)
        with self.core_dma.recorder:
            self.core_dma.prepare_record(self.trace_name)
            with self.core_dma.recorder:
                pass

    @kernel
    def invalidate(self, mode: int32):
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
        channel = exp.ttl_out.channel

        for use_handle in [False, True]:
            exp.record(use_handle)
            get_analyzer_dump(core_host)  # clear analyzer buffer
            exp.playback(use_handle)

            dump = decode_dump(get_analyzer_dump(core_host))
            self.assertEqual(len(dump.messages), 3)
            self.assertIsInstance(dump.messages[-1], StoppedMessage)
            self.assertIsInstance(dump.messages[0], OutputMessage)
            self.assertEqual(dump.messages[0].channel, channel)
            self.assertEqual(dump.messages[0].address, 0)
            self.assertEqual(dump.messages[0].data, 1)
            self.assertIsInstance(dump.messages[1], OutputMessage)
            self.assertEqual(dump.messages[1].channel, channel)
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
        self.assertLess(dt/count, 11*us)

    def test_dma_playback_time(self):
        exp = self.create(_DMA)
        is_zynq = exp.core.target == "cortexa9"
        count = 20000
        exp.record_many(40)
        exp.playback_many(count, is_zynq)
        dt = self.dataset_mgr.get("dma_playback_time")
        print("dt={}, dt/count={}".format(dt, dt/count))
        if is_zynq:
            self.assertLess(dt/count, 6.2*us)
        else:
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
