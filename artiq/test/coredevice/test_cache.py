import unittest

from numpy import int32

from artiq.experiment import *
from artiq.coredevice.core import Core
from artiq.coredevice.cache import CoreCache
from artiq.coredevice.exceptions import CacheError
from artiq.test.hardware_testbench import ExperimentCase


# NAC3TODO @nac3
class _Cache(EnvExperiment):
    core: KernelInvariant[Core]
    core_cache: KernelInvariant[CoreCache]

    def build(self):
        self.setattr_device("core")
        self.setattr_device("core_cache")

    @kernel
    def get(self, key: str) -> list[int32]:
        return self.core_cache.get(key)

    @kernel
    def put(self, key: str, value: list[int32]):
        self.core_cache.put(key, value)

    @kernel
    def get_put(self, key: str, value: list[int32]):
        self.get(key)
        self.put(key, value)


@unittest.skip("NAC3TODO https://git.m-labs.hk/M-Labs/nac3/issues/299")
class CacheTest(ExperimentCase):
    def test_get_empty(self):
        exp = self.create(_Cache)
        self.assertEqual(exp.get("x1"), [])

    def test_put_get(self):
        exp = self.create(_Cache)
        exp.put("x2", [1, 2, 3])
        self.assertEqual(exp.get("x2"), [1, 2, 3])

    def test_replace(self):
        exp = self.create(_Cache)
        exp.put("x3", [1, 2, 3])
        exp.put("x3", [1, 2, 3, 4, 5])
        self.assertEqual(exp.get("x3"), [1, 2, 3, 4, 5])

    def test_borrow(self):
        exp = self.create(_Cache)
        if exp.core.target == "cortexa9":
            self.skipTest("Zynq port memory management does not need CacheError")
        exp.put("x4", [1, 2, 3])
        with self.assertRaises(CacheError):
            exp.get_put("x4", [])
