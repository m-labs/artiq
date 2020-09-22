import os
import time
import unittest
import numpy

from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase

# large: 1MB payload
# small: 1KB payload
bytes_large = b"\x00" * (1 << 20)
bytes_small = b"\x00" * (1 << 10)

list_large = [123] * (1 << 18)
list_small = [123] * (1 << 8)

array_large = numpy.array(list_large, numpy.int32)
array_small = numpy.array(list_small, numpy.int32)

byte_list_large = [True] * (1 << 20)
byte_list_small = [True] * (1 << 10)

received_bytes = 0
time_start = 0
time_end = 0

class _Transfer(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.count = 10
        self.h2d = [0.0] * self.count
        self.d2h = [0.0] * self.count

    @rpc
    def get_bytes(self, large: TBool) -> TBytes:
        if large:
            return bytes_large
        else:
            return bytes_small

    @rpc
    def get_list(self, large: TBool) -> TList(TInt32):
        if large:
            return list_large
        else:
            return list_small

    @rpc
    def get_byte_list(self, large: TBool) -> TList(TBool):
        if large:
            return byte_list_large
        else:
            return byte_list_small

    @rpc
    def get_array(self, large: TBool) -> TArray(TInt32):
        if large:
            return array_large
        else:
            return array_small

    @rpc
    def get_string_list(self) -> TList(TStr):
        return string_list

    @rpc
    def sink(self, data):
        pass

    @rpc(flags={"async"})
    def sink_async(self, data):
        global received_bytes, time_start, time_end
        if received_bytes == 0:
            time_start = time.time()
        received_bytes += len(data)
        if received_bytes == (1024 ** 2)*128:
            time_end = time.time()

    @rpc
    def get_async_throughput(self) -> TFloat:
        return 128.0 / (time_end - time_start)

    @kernel
    def test_bytes(self, large):
        def inner():
            t0 = self.core.get_rtio_counter_mu()
            data = self.get_bytes(large)
            t1 = self.core.get_rtio_counter_mu()
            self.sink(data)
            t2 = self.core.get_rtio_counter_mu()
            self.h2d[i] = self.core.mu_to_seconds(t1 - t0)
            self.d2h[i] = self.core.mu_to_seconds(t2 - t1)

        for i in range(self.count):
            inner()
        return (self.h2d, self.d2h)

    @kernel
    def test_byte_list(self, large):
        def inner():
            t0 = self.core.get_rtio_counter_mu()
            data = self.get_byte_list(large)
            t1 = self.core.get_rtio_counter_mu()
            self.sink(data)
            t2 = self.core.get_rtio_counter_mu()
            self.h2d[i] = self.core.mu_to_seconds(t1 - t0)
            self.d2h[i] = self.core.mu_to_seconds(t2 - t1)

        for i in range(self.count):
            inner()
        return (self.h2d, self.d2h)

    @kernel
    def test_list(self, large):
        def inner():
            t0 = self.core.get_rtio_counter_mu()
            data = self.get_list(large)
            t1 = self.core.get_rtio_counter_mu()
            self.sink(data)
            t2 = self.core.get_rtio_counter_mu()
            self.h2d[i] = self.core.mu_to_seconds(t1 - t0)
            self.d2h[i] = self.core.mu_to_seconds(t2 - t1)

        for i in range(self.count):
            inner()
        return (self.h2d, self.d2h)

    @kernel
    def test_array(self, large):
        def inner():
            t0 = self.core.get_rtio_counter_mu()
            data = self.get_array(large)
            t1 = self.core.get_rtio_counter_mu()
            self.sink(data)
            t2 = self.core.get_rtio_counter_mu()
            self.h2d[i] = self.core.mu_to_seconds(t1 - t0)
            self.d2h[i] = self.core.mu_to_seconds(t2 - t1)

        for i in range(self.count):
            inner()
        return (self.h2d, self.d2h)

    @kernel
    def test_async(self):
        data = self.get_bytes(True)
        for _ in range(128):
            self.sink_async(data)
        return self.get_async_throughput()

class TransferTest(ExperimentCase):
    @classmethod
    def setUpClass(self):
        self.results = []

    @classmethod
    def tearDownClass(self):
        if len(self.results) == 0:
            return
        max_length = max(max(len(row[0]) for row in self.results), len("Test"))

        def pad(name):
            nonlocal max_length
            return name + " " * (max_length - len(name))
        print()
        print("| {} | Mean (MiB/s) |  std (MiB/s) |".format(pad("Test")))
        print("| {} | ------------ | ------------ |".format("-" * max_length))
        for v in self.results:
            print("| {} | {:>12.2f} | {:>12.2f} |".format(
                pad(v[0]), v[1], v[2]))

    def test_bytes_large(self):
        exp = self.create(_Transfer)
        results = exp.test_bytes(True)
        host_to_device = (1 << 20) / numpy.array(results[0], numpy.float64)
        device_to_host = (1 << 20) / numpy.array(results[1], numpy.float64)
        host_to_device /= 1024*1024
        device_to_host /= 1024*1024
        self.results.append(["Bytes (1MB) H2D", host_to_device.mean(),
                             host_to_device.std()])
        self.results.append(["Bytes (1MB) D2H", device_to_host.mean(),
                             device_to_host.std()])

    def test_bytes_small(self):
        exp = self.create(_Transfer)
        results = exp.test_bytes(False)
        host_to_device = (1 << 10) / numpy.array(results[0], numpy.float64)
        device_to_host = (1 << 10) / numpy.array(results[1], numpy.float64)
        host_to_device /= 1024*1024
        device_to_host /= 1024*1024
        self.results.append(["Bytes (1KB) H2D", host_to_device.mean(),
                             host_to_device.std()])
        self.results.append(["Bytes (1KB) D2H", device_to_host.mean(),
                             device_to_host.std()])

    def test_byte_list_large(self):
        exp = self.create(_Transfer)
        results = exp.test_byte_list(True)
        host_to_device = (1 << 20) / numpy.array(results[0], numpy.float64)
        device_to_host = (1 << 20) / numpy.array(results[1], numpy.float64)
        host_to_device /= 1024*1024
        device_to_host /= 1024*1024
        self.results.append(["Bytes List (1MB) H2D", host_to_device.mean(),
                             host_to_device.std()])
        self.results.append(["Bytes List (1MB) D2H", device_to_host.mean(),
                             device_to_host.std()])

    def test_byte_list_small(self):
        exp = self.create(_Transfer)
        results = exp.test_byte_list(False)
        host_to_device = (1 << 10) / numpy.array(results[0], numpy.float64)
        device_to_host = (1 << 10) / numpy.array(results[1], numpy.float64)
        host_to_device /= 1024*1024
        device_to_host /= 1024*1024
        self.results.append(["Bytes List (1KB) H2D", host_to_device.mean(),
                             host_to_device.std()])
        self.results.append(["Bytes List (1KB) D2H", device_to_host.mean(),
                             device_to_host.std()])

    def test_list_large(self):
        exp = self.create(_Transfer)
        results = exp.test_list(True)
        host_to_device = (1 << 20) / numpy.array(results[0], numpy.float64)
        device_to_host = (1 << 20) / numpy.array(results[1], numpy.float64)
        host_to_device /= 1024*1024
        device_to_host /= 1024*1024
        self.results.append(["I32 List (1MB) H2D", host_to_device.mean(),
                             host_to_device.std()])
        self.results.append(["I32 List (1MB) D2H", device_to_host.mean(),
                             device_to_host.std()])

    def test_list_small(self):
        exp = self.create(_Transfer)
        results = exp.test_list(False)
        host_to_device = (1 << 10) / numpy.array(results[0], numpy.float64)
        device_to_host = (1 << 10) / numpy.array(results[1], numpy.float64)
        host_to_device /= 1024*1024
        device_to_host /= 1024*1024
        self.results.append(["I32 List (1KB) H2D", host_to_device.mean(),
                             host_to_device.std()])
        self.results.append(["I32 List (1KB) D2H", device_to_host.mean(),
                             device_to_host.std()])

    def test_array_large(self):
        exp = self.create(_Transfer)
        results = exp.test_array(True)
        host_to_device = (1 << 20) / numpy.array(results[0], numpy.float64)
        device_to_host = (1 << 20) / numpy.array(results[1], numpy.float64)
        host_to_device /= 1024*1024
        device_to_host /= 1024*1024
        self.results.append(["I32 Array (1MB) H2D", host_to_device.mean(),
                             host_to_device.std()])
        self.results.append(["I32 Array (1MB) D2H", device_to_host.mean(),
                             device_to_host.std()])

    def test_array_small(self):
        exp = self.create(_Transfer)
        results = exp.test_array(False)
        host_to_device = (1 << 10) / numpy.array(results[0], numpy.float64)
        device_to_host = (1 << 10) / numpy.array(results[1], numpy.float64)
        host_to_device /= 1024*1024
        device_to_host /= 1024*1024
        self.results.append(["I32 Array (1KB) H2D", host_to_device.mean(),
                             host_to_device.std()])
        self.results.append(["I32 Array (1KB) D2H", device_to_host.mean(),
                             device_to_host.std()])

    def test_async_throughput(self):
        exp = self.create(_Transfer)
        results = exp.test_async()
        print("Async throughput: {:>6.2f}MiB/s".format(results))

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
