from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase


class Collision(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("spi0")

    @kernel
    def run(self):
        self.core.break_realtime()
        t = now_mu()
        self.spi0.set_config_mu()
        at_mu(t)
        self.spi0.set_config_mu()


class Busy(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("spi0")
        self.setattr_device("led")

    @kernel
    def run(self):
        self.core.break_realtime()
        t = now_mu()
        self.spi0.set_config_mu()
        at_mu(t + self.spi0.ref_period_mu)
        self.spi0.set_config_mu()  # causes the error
        self.led.on()
        self.led.sync()            # registers the error
        self.core.break_realtime()
        self.spi0.set_config_mu()  # raises the error


class SPITest(ExperimentCase):
    def test_collision(self):
        with self.assertRaises(RTIOCollision):
            self.execute(Collision)

    def test_busy(self):
        with self.assertRaises(RTIOBusy):
            self.execute(Busy)
