from artiq.experiment import *


class SAWGTest(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_sma_out")

        self.setattr_device("sawg0")
        self.setattr_device("sawg1")
        self.setattr_device("sawg2")
        self.setattr_device("sawg3")

    @kernel
    def run(self):
        self.core.reset()

        while True:
            self.sawg0.amplitude1.set(0.)
            self.sawg0.frequency0.set(0*MHz)
            self.sawg1.amplitude1.set(0.)
            self.sawg1.frequency0.set(0*MHz)
            delay(20*ms)

            self.sawg0.amplitude1.set(.4)
            self.sawg0.frequency0.set(10*MHz)
            self.sawg0.phase0.set(0.)
            self.sawg1.amplitude1.set(.4)
            self.sawg1.frequency0.set(10*MHz)
            self.sawg1.phase0.set(0.)
            self.ttl_sma_out.pulse(200*ns)
            self.sawg1.amplitude1.set(.1)
            delay(200*ns)
            self.sawg1.amplitude1.set(-.4)
            self.ttl_sma_out.pulse(200*ns)
            self.sawg1.amplitude1.set(.4)
            delay(200*ns)
            self.sawg1.phase0.set(.25)
            self.ttl_sma_out.pulse(200*ns)
            self.sawg1.phase0.set(.5)
            delay(200*ns)
            self.sawg0.phase0.set(.5)
            self.ttl_sma_out.pulse(200*ns)
            self.sawg1.frequency0.set(30*MHz)
            delay(200*ns)
            self.sawg1.frequency0.set(10*MHz)
            self.sawg1.phase0.set(0.)
            self.ttl_sma_out.pulse(200*ns)
