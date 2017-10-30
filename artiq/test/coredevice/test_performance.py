import os
import unittest

from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase


artiq_low_latency = os.getenv("ARTIQ_LOW_LATENCY")


class _Transfer(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.data = b"\x00"*(10**6)

    @rpc
    def source(self) -> TBytes:
        return self.data

    @rpc(flags={"async"})
    def sink(self, data):
        assert data == self.data

    @kernel
    def host_to_device(self):
        t0 = self.core.get_rtio_counter_mu()
        data = self.source()
        t1 = self.core.get_rtio_counter_mu()
        return len(data)/self.core.mu_to_seconds(t1-t0)

    @kernel
    def device_to_host(self):
        t0 = self.core.get_rtio_counter_mu()
        self.sink(self.data)
        t1 = self.core.get_rtio_counter_mu()
        return len(self.data)/self.core.mu_to_seconds(t1-t0)


class TransferTest(ExperimentCase):
    @unittest.skipUnless(artiq_low_latency,
                         "timings are dependent on CPU load and network conditions")
    def test_host_to_device(self):
        exp = self.create(_Transfer)
        host_to_device_rate = exp.host_to_device()
        print(host_to_device_rate, "B/s")
        self.assertGreater(host_to_device_rate, 2.2e6)

    @unittest.skipUnless(artiq_low_latency,
                         "timings are dependent on CPU load and network conditions")
    def test_device_to_host(self):
        exp = self.create(_Transfer)
        device_to_host_rate = exp.device_to_host()
        print(device_to_host_rate, "B/s")
        self.assertGreater(device_to_host_rate, 2.2e6)
