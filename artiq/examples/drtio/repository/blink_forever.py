from artiq.experiment import *


class BlinkForever(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("rled0")

    @kernel
    def run(self):
        self.core.reset()
        while True:
            self.rled0.pulse(100*ms)
            delay(100*ms)
