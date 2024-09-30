import os
import time
import unittest
from typing import Literal

import numpy
from numpy import int32, float64, ndarray

from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase
from artiq.coredevice.core import Core


bool_list_large = [True] * (1 << 20)
bool_list_small = [True] * (1 << 10)

# large: 1MB payload
# small: 1KB payload
list_large = [123] * (1 << 18)
list_small = [123] * (1 << 8)

array_large = numpy.array(list_large, int32)
array_small = numpy.array(list_small, int32)

received_bytes = 0
time_start = 0
time_end = 0


@nac3
class _Transfer(EnvExperiment):
    core: KernelInvariant[Core]
    count: KernelInvariant[int32]
    h2d: Kernel[list[float]]
    d2h: Kernel[list[float]]

    def build(self):
        self.setattr_device("core")
        self.count = 10
        self.h2d = [0.0] * self.count
        self.d2h = [0.0] * self.count

    @rpc
    def get_list(self, large: bool) -> list[int32]:
        if large:
            return list_large
        else:
            return list_small

    @rpc
    def get_bool_list(self, large: bool) -> list[bool]:
        if large:
            return bool_list_large
        else:
            return bool_list_small

    @rpc
    def get_array(self, large: bool) -> ndarray[int32, Literal[1]]:
        if large:
            return array_large
        else:
            return array_small

    @rpc
    def get_string_list(self) -> list[str]:
        return string_list

    @rpc
    def sink_bool_list(self, data: list[bool]):
        pass

    @rpc
    def sink_list(self, data: list[int32]):
        pass

    @rpc
    def sink_array(self, data: ndarray[int32, Literal[1]]):
        pass

    @rpc(flags={"async"})
    def sink_async(self, data: list[int32]):
        global received_bytes, time_start, time_end
        if received_bytes == 0:
            time_start = time.time()
        received_bytes += 4*len(data)
        if received_bytes == (1024 ** 2)*128:
            time_end = time.time()

    def get_async_throughput(self) -> float:
        return 128.0 / (time_end - time_start)

    @kernel
    def test_bool_list(self, large: bool):
        for i in range(self.count):
            t0 = self.core.get_rtio_counter_mu()
            data = self.get_bool_list(large)
            t1 = self.core.get_rtio_counter_mu()
            self.sink_bool_list(data)
            t2 = self.core.get_rtio_counter_mu()
            self.h2d[i] = self.core.mu_to_seconds(t1 - t0)
            self.d2h[i] = self.core.mu_to_seconds(t2 - t1)

    @kernel
    def test_list(self, large: bool):
        for i in range(self.count):
            t0 = self.core.get_rtio_counter_mu()
            data = self.get_list(large)
            t1 = self.core.get_rtio_counter_mu()
            self.sink_list(data)
            t2 = self.core.get_rtio_counter_mu()
            self.h2d[i] = self.core.mu_to_seconds(t1 - t0)
            self.d2h[i] = self.core.mu_to_seconds(t2 - t1)

    @kernel
    def test_array(self, large: bool):
        for i in range(self.count):
            t0 = self.core.get_rtio_counter_mu()
            data = self.get_array(large)
            t1 = self.core.get_rtio_counter_mu()
            self.sink_array(data)
            t2 = self.core.get_rtio_counter_mu()
            self.h2d[i] = self.core.mu_to_seconds(t1 - t0)
            self.d2h[i] = self.core.mu_to_seconds(t2 - t1)

    @kernel
    def test_async(self):
        data = self.get_list(True)
        for _ in range(128):
            self.sink_async(data)


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

    def test_bool_list_large(self):
        exp = self.create(_Transfer)
        exp.test_bool_list(True)
        host_to_device = (1 << 20) / numpy.array(exp.h2d, float64)
        device_to_host = (1 << 20) / numpy.array(exp.d2h, float64)
        host_to_device /= 1024*1024
        device_to_host /= 1024*1024
        self.results.append(["Bool List (1MB) H2D", host_to_device.mean(),
                             host_to_device.std()])
        self.results.append(["Bool List (1MB) D2H", device_to_host.mean(),
                             device_to_host.std()])

    def test_bool_list_small(self):
        exp = self.create(_Transfer)
        exp.test_bool_list(False)
        host_to_device = (1 << 10) / numpy.array(exp.h2d, float64)
        device_to_host = (1 << 10) / numpy.array(exp.d2h, float64)
        host_to_device /= 1024*1024
        device_to_host /= 1024*1024
        self.results.append(["Bool List (1KB) H2D", host_to_device.mean(),
                             host_to_device.std()])
        self.results.append(["Bool List (1KB) D2H", device_to_host.mean(),
                             device_to_host.std()])

    def test_list_large(self):
        exp = self.create(_Transfer)
        exp.test_list(True)
        host_to_device = (1 << 20) / numpy.array(exp.h2d, float64)
        device_to_host = (1 << 20) / numpy.array(exp.d2h, float64)
        host_to_device /= 1024*1024
        device_to_host /= 1024*1024
        self.results.append(["I32 List (1MB) H2D", host_to_device.mean(),
                             host_to_device.std()])
        self.results.append(["I32 List (1MB) D2H", device_to_host.mean(),
                             device_to_host.std()])

    def test_list_small(self):
        exp = self.create(_Transfer)
        exp.test_list(False)
        host_to_device = (1 << 10) / numpy.array(exp.h2d, float64)
        device_to_host = (1 << 10) / numpy.array(exp.d2h, float64)
        host_to_device /= 1024*1024
        device_to_host /= 1024*1024
        self.results.append(["I32 List (1KB) H2D", host_to_device.mean(),
                             host_to_device.std()])
        self.results.append(["I32 List (1KB) D2H", device_to_host.mean(),
                             device_to_host.std()])

    def test_array_large(self):
        exp = self.create(_Transfer)
        exp.test_array(True)
        host_to_device = (1 << 20) / numpy.array(exp.h2d, float64)
        device_to_host = (1 << 20) / numpy.array(exp.d2h, float64)
        host_to_device /= 1024*1024
        device_to_host /= 1024*1024
        self.results.append(["I32 Array (1MB) H2D", host_to_device.mean(),
                             host_to_device.std()])
        self.results.append(["I32 Array (1MB) D2H", device_to_host.mean(),
                             device_to_host.std()])

    def test_array_small(self):
        exp = self.create(_Transfer)
        exp.test_array(False)
        host_to_device = (1 << 10) / numpy.array(exp.h2d, float64)
        device_to_host = (1 << 10) / numpy.array(exp.d2h, float64)
        host_to_device /= 1024*1024
        device_to_host /= 1024*1024
        self.results.append(["I32 Array (1KB) H2D", host_to_device.mean(),
                             host_to_device.std()])
        self.results.append(["I32 Array (1KB) D2H", device_to_host.mean(),
                             device_to_host.std()])

    def test_async_throughput(self):
        exp = self.create(_Transfer)
        exp.test_async()
        results = exp.get_async_throughput()
        print("Async throughput: {:>6.2f}MiB/s".format(results))


@nac3
class _KernelOverhead(EnvExperiment):
    core: KernelInvariant[Core]

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
