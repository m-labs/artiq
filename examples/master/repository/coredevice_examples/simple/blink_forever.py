from artiq import *


class BlinkForever(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("led")

    @kernel
    def run(self):
        while True:
            self.led.pulse(100*ms)
            delay(100*ms)
