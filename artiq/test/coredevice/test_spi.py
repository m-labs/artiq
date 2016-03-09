from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase


class Busy(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("spi0")
        self.setattr_device("led")

    @kernel
    def run(self):
        self.spi0.set_config_mu()
        delay(-8*ns)
        self.spi0.set_config_mu()  # causes the error
        self.led.on()
        self.led.sync()            # registers the error
        self.core.break_realtime()
        self.spi0.set_config_mu()  # raises the error


class SPITest(ExperimentCase):
    def test_busy(self):
        self.execute(Busy)
