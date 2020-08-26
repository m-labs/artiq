import os
import time
import unittest
import numpy

from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase


class _Transfer(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.data = b"\x00"*(10**6)

    @rpc
    def source(self) -> TBytes:
        return self.data

    @rpc
    def source_byte_list(self) -> TList(TBool):
        return [True] * (1 << 15)

    @rpc
    def source_list(self) -> TList(TInt32):
        return [123] * (1 << 15)

    @rpc
    def source_array(self) -> TArray(TInt32):
        return numpy.array([0] * (1 << 15), numpy.int32)

    @rpc
    def sink(self, data):
        pass

    @rpc
    def sink_list(self, data):
        pass

    @rpc
    def sink_array(self, data):
        pass

    @kernel
    def host_to_device(self):
        t0 = self.core.get_rtio_counter_mu()
        data = self.source()
        t1 = self.core.get_rtio_counter_mu()
        return len(data)/self.core.mu_to_seconds(t1-t0)

    @kernel
    def host_to_device_list(self):
        t0 = self.core.get_rtio_counter_mu()
        data = self.source_list()
        t1 = self.core.get_rtio_counter_mu()
        return 4 * len(data)/self.core.mu_to_seconds(t1-t0)

    @kernel
    def host_to_device_array(self):
        t0 = self.core.get_rtio_counter_mu()
        data = self.source_array()
        t1 = self.core.get_rtio_counter_mu()
        return 4 * len(data)/self.core.mu_to_seconds(t1-t0)

    @kernel
    def host_to_device_byte_list(self):
        t0 = self.core.get_rtio_counter_mu()
        data = self.source_byte_list()
        t1 = self.core.get_rtio_counter_mu()
        return len(data)/self.core.mu_to_seconds(t1-t0)

    @kernel
    def device_to_host(self):
        t0 = self.core.get_rtio_counter_mu()
        self.sink(self.data)
        t1 = self.core.get_rtio_counter_mu()
        return len(self.data)/self.core.mu_to_seconds(t1-t0)

    @kernel
    def device_to_host_list(self):
        #data = [[0]*8 for _ in range(1 << 12)]
        data = [0]*(1 << 15)
        t0 = self.core.get_rtio_counter_mu()
        self.sink_list(data)
        t1 = self.core.get_rtio_counter_mu()
        return ((len(data)*4) /
                self.core.mu_to_seconds(t1-t0))

    @kernel
    def device_to_host_array(self):
        data = self.source_array()
        t0 = self.core.get_rtio_counter_mu()
        self.sink_array(data)
        t1 = self.core.get_rtio_counter_mu()
        return ((len(data)*4) /
                self.core.mu_to_seconds(t1-t0))


class TransferTest(ExperimentCase):
    def test_host_to_device(self):
        exp = self.create(_Transfer)
        host_to_device_rate = exp.host_to_device()
        print(host_to_device_rate/(1024*1024), "MiB/s")
        self.assertGreater(host_to_device_rate, 2.0e6)

    def test_host_to_device_byte_list(self):
        exp = self.create(_Transfer)
        host_to_device_rate = exp.host_to_device_byte_list()
        print(host_to_device_rate/(1024*1024), "MiB/s")
        self.assertGreater(host_to_device_rate, 2.0e6)

    def test_host_to_device_list(self):
        exp = self.create(_Transfer)
        host_to_device_rate = exp.host_to_device_list()
        print(host_to_device_rate/(1024*1024), "MiB/s")
        self.assertGreater(host_to_device_rate, 2.0e6)

    def test_host_to_device_array(self):
        exp = self.create(_Transfer)
        host_to_device_rate = exp.host_to_device_array()
        print(host_to_device_rate/(1024*1024), "MiB/s")
        self.assertGreater(host_to_device_rate, 2.0e6)

    def test_device_to_host(self):
        exp = self.create(_Transfer)
        device_to_host_rate = exp.device_to_host()
        print(device_to_host_rate/(1024*1024), "MiB/s")
        self.assertGreater(device_to_host_rate, 2.2e6)

    def test_device_to_host_list(self):
        exp = self.create(_Transfer)
        rate = exp.device_to_host_list()
        print(rate/(1024*1024), "MiB/s")
        self.assertGreater(rate, .15e6)

    def test_device_to_host_array(self):
        exp = self.create(_Transfer)
        rate = exp.device_to_host_array()
        print(rate/(1024*1024), "MiB/s")
        self.assertGreater(rate, .15e6)


class _KernelOverhead(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    def kernel_overhead(self):
        n = 100
        t0 = time.monotonic()
        for _ in range(n):
            self.dummy_kernel()
        t1 = time.monotonic()
        return (t1-t0)/n

    @kernel
    def dummy_kernel(self):
        pass


class KernelOverheadTest(ExperimentCase):
    def test_kernel_overhead(self):
        exp = self.create(_KernelOverhead)
        kernel_overhead = exp.kernel_overhead()
        print(kernel_overhead, "s")
        self.assertGreater(kernel_overhead, 0.001)
        self.assertLess(kernel_overhead, 0.5)
