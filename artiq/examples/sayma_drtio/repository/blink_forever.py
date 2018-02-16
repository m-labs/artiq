from artiq.experiment import *


class BlinkForever(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.rleds = [self.get_device("rled" + str(i)) for i in range(4)]
        self.leds = [self.get_device("led" + str(i)) for i in range(4)]

    @kernel
    def run(self):
        self.core.reset()

        while True:
            with parallel:
                for led in self.leds:
                    led.pulse(250*ms)
                for led in self.rleds:
                    led.pulse(250*ms)
            t = now_mu()
            for led in self.leds:
                at_mu(t)
                led.pulse(500*ms)
            for led in self.rleds:
                at_mu(t)
                led.pulse(500*ms)
            delay(250*ms)
