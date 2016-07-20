from artiq.experiment import *


class Handover(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("led")

    @kernel
    def blink_once(self):
        delay(250*ms)
        self.led.pulse(250*ms)

    def run(self):
        self.core.reset()
        while True:
            self.blink_once()
