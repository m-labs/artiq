from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase


class WrongError(Exception):
    pass


class Collision(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("spi0")

    @kernel
    def run(self):
        self.core.break_realtime()
        t = now_mu()
        try:
            self.spi0.set_config_mu()
        except RTIOBusy:
            raise WrongError()
        at_mu(t)
        self.spi0.set_config_mu()


class Busy(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("spi0")
        self.setattr_device("led")

    @kernel
    def run(self):
        try:
            self.core.break_realtime()
            self.spi0.set_config_mu()
            t = now_mu()
            self.spi0.set_config_mu()
            at_mu(t + self.spi0.ref_period_mu)
            self.spi0.set_config_mu()  # causes the error
            self.led.on()
            self.led.sync()            # registers the error
            self.core.break_realtime()
        except RTIOBusy:
            raise WrongError()         # we don't expect RTIOBusy so far
        self.spi0.set_config_mu()  # raises the error


class DrainErrors(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("spi0")
        self.setattr_device("led")

    @kernel
    def run(self):
        while True:
            try:
                self.core.break_realtime()
                delay(100*us)
                self.spi0.set_config_mu()
                self.led.on()
                self.led.sync()
                self.core.break_realtime()
                self.spi0.set_config_mu()
                self.led.off()
                return
            except:
                pass


class SPITest(ExperimentCase):
    def tearDown(self):
        self.execute(DrainErrors)
        ExperimentCase.tearDown(self)

    def test_collision(self):
        with self.assertRaises(RTIOCollision):
            self.execute(Collision)

    def test_busy(self):
        with self.assertRaises(RTIOBusy):
            self.execute(Busy)
