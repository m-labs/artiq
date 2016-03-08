import os, unittest

from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase


class I2CSwitch(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("i2c_switch")

    @kernel
    def run(self):
        passed = True
        for i in range(8):
            self.i2c_switch.set(i)
            if self.i2c_switch.readback() != 1 << i:
                passed = False
        self.set_dataset("passed", passed)


class I2CTest(ExperimentCase):
    def test_i2c_switch(self):
        self.execute(I2CSwitch)
        self.assertTrue(self.dataset_mgr.get("passed"))
