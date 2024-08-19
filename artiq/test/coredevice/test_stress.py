import unittest

from numpy import int32

from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase
from artiq.coredevice.core import Core

@nac3
class _Stress(EnvExperiment):
    core: KernelInvariant[Core]

    def build(self):
        self.setattr_device("core")

    # NAC3TODO https://git.m-labs.hk/M-Labs/nac3/issues/182
    @rpc #(flags={"async"})
    def sink(self, data: int32):
        pass

    @kernel
    def async_rpc(self, n: int32):
        for _ in range(n):
            self.sink(0)


class StressTest(ExperimentCase):
    def test_async_rpc(self):
        exp = self.create(_Stress)
        exp.async_rpc(16000)
