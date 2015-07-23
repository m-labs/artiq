from artiq import *


class Handover(EnvExperiment):
    def build(self):
        self.attr_device("core")
        self.attr_device("led")

    @kernel
    def blink_once(self):
        self.led.pulse(250*ms)
        delay(250*ms)

    def run(self):
        while True:
            self.blink_once()
