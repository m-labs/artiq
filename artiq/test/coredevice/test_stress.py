import os
import time
import unittest

from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase


class _Stress(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    @rpc(flags={"async"})
    def sink(self, data):
        pass

    @kernel
    def async_rpc(self, n):
        for _ in range(n):
            self.sink(b"")


class StressTest(ExperimentCase):
    def test_async_rpc(self):
        exp = self.create(_Stress)
        exp.async_rpc(16000)
