from artiq.experiment import *


class SAWGTest(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("led")

        self.setattr_device("sawg0")
        self.setattr_device("sawg1")
        self.setattr_device("sawg2")
        self.setattr_device("sawg3")

    @kernel
    def run(self):
        self.core.break_realtime()

        self.sawg0.amplitude1.set(.1)
        self.sawg0.frequency0.set(10*MHz)
        self.sawg0.phase0.set(0.)
        self.sawg1.amplitude1.set(-.9)
        self.sawg1.frequency0.set(20*MHz)
        self.sawg1.phase0.set(0.)
        self.sawg2.amplitude1.set(.5)
        self.sawg2.frequency0.set(30*MHz)
        self.sawg2.phase0.set(0.)
        self.sawg3.amplitude1.set(.5)
        self.sawg3.frequency0.set(30*MHz)
        self.sawg3.phase0.set(.5)

        for i in range(10):
            self.led.pulse(100*ms)
            delay(100*ms)
