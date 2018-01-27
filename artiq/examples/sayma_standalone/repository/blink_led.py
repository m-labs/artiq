from artiq.experiment import *


class BlinkSaymaLED(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("led0")

    @kernel
    def run(self):
        self.core.reset()
        while True:
            for _ in range(3):
                self.led0.pulse(100*ms)
                delay(100*ms)
            delay(500*ms)
