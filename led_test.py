from artiq.experiment import *
from artiq.language.units import us, ms

class DAC_Init(EnvExperiment):

    def build(self):
        self.setattr_device("core")
        self.setattr_device("led1")
        self.setattr_device("led2")
        self.setattr_device("shuttler0_led0")
        self.setattr_device("shuttler0_led1")

    @kernel
    def run(self):
        self.core.reset()
        while True:
            self.led1.pulse(100*ms)
            self.led2.pulse(100*ms)
            self.shuttler0_led0.pulse(100*ms)
            self.shuttler0_led1.pulse(100*ms)
            delay(100*ms)