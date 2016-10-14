from artiq.experiment import *


class SAWGTest(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("led")
        self.setattr_device("ttl_sma")

        self.setattr_device("sawg0")
        self.setattr_device("sawg1")
        self.setattr_device("sawg2")
        self.setattr_device("sawg3")

    @kernel
    def run(self):
        self.core.break_realtime()
        self.ttl_sma.output()

        while True:
            self.sawg0.set_amplitude(0.)
            self.sawg0.set_frequency(0*MHz)
            self.sawg1.set_amplitude(0.)
            self.sawg1.set_frequency(0*MHz)
            delay(20*ms)

            self.sawg0.set_amplitude(.4)
            self.sawg0.set_frequency(10*MHz)
            self.sawg0.set_phase(0.)
            self.sawg1.set_amplitude(.4)
            self.sawg1.set_frequency(10*MHz)
            self.sawg1.set_phase(0.)
            self.ttl_sma.pulse(200*ns)
            self.sawg1.set_amplitude(.1)
            delay(200*ns)
            self.sawg1.set_amplitude(-.4)
            self.ttl_sma.pulse(200*ns)
            self.sawg1.set_amplitude(.4)
            delay(200*ns)
            self.sawg1.set_phase(.25)
            self.ttl_sma.pulse(200*ns)
            self.sawg1.set_phase(.5)
            delay(200*ns)
            self.sawg0.set_phase(.5)
            self.ttl_sma.pulse(200*ns)
            self.sawg1.set_frequency(30*MHz)
            delay(200*ns)
            self.sawg1.set_frequency(10*MHz)
            self.sawg1.set_phase(0.)
            self.ttl_sma.pulse(200*ns)
