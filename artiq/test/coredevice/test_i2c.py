import os, unittest

from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase
from artiq.coredevice.exceptions import I2CError
from artiq.coredevice.i2c import I2CSwitch, i2c_read_byte


class I2CSwitchTest(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("i2c_switch")

    @kernel
    def run(self):
        passed = True
        for i in range(8):
            self.i2c_switch.set(i)
            # this will work only with pca9548 (like on kc705)
            # otherwise we cannot guarantee exact readback values
            if i2c_read_byte(self.i2c_switch.busno, self.i2c_switch.address) != 1 << i:
                passed = False
        self.set_dataset("passed", passed)


class NonexistentI2CBus(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("i2c_switch")  # HACK: only run this test on boards with I2C
        self.broken_switch = I2CSwitch(self._HasEnvironment__device_mgr, 255)

    @kernel
    def run(self):
        self.broken_switch.set(0)


class I2CTest(ExperimentCase):
    def test_i2c_switch(self):
        self.execute(I2CSwitchTest)
        self.assertTrue(self.dataset_mgr.get("passed"))

    def test_nonexistent_bus(self):
        with self.assertRaises(I2CError):
            self.execute(NonexistentI2CBus)
