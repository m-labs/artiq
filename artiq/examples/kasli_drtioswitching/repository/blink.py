from artiq.experiment import *


class Blink(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.leds = [self.get_device("led0"), self.get_device("led2")]

    @kernel
    def run(self):
        self.core.reset()

        while True:
            for led in self.leds:
                led.pulse(200*ms)
                delay(200*ms)
