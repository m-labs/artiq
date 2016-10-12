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

        self.sawg0.set_amplitude(.1)
        self.sawg0.set_frequency(10*MHz)
        self.sawg0.set_phase(0.)
        self.sawg1.set_amplitude(-.9)
        self.sawg1.set_frequency(20*MHz)
        self.sawg1.set_phase(0.)
        self.sawg2.set_amplitude(.5)
        self.sawg2.set_frequency(30*MHz)
        self.sawg2.set_phase(0.)
        self.sawg3.set_amplitude(.5)
        self.sawg3.set_frequency(30*MHz)
        self.sawg3.set_phase(.5)

        for i in range(10):
            self.led.pulse(100*ms)
            delay(100*ms)
