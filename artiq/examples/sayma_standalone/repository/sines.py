from artiq.experiment import *


class SAWGTest(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_sma_out")
        self.sawgs = [self.get_device("sawg"+str(i)) for i in range(8)]

    @kernel
    def run(self):
        self.core.reset()

        for sawg in self.sawgs:
            delay(1*ms)
            sawg.amplitude1.set(.4)
            # Do not use a sub-multiple of oscilloscope sample rates.
            sawg.frequency0.set(49*MHz)

        while True:
            delay(0.5*ms)
            self.ttl_sma_out.pulse(0.5*ms)
