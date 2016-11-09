from artiq.experiment import *


class BlinkForever(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.leds = [self.get_device("rled" + str(i)) for i in range(8)]

    @kernel
    def run(self):
        #self.core.reset()
        self.core.break_realtime()

        while True:
            for led in self.leds:
                led.pulse(250*ms)
            t = now_mu()
            for led in self.leds:
                at_mu(t)
                led.pulse(500*ms)
            delay(250*ms)
