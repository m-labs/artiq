from artiq.experiment import *


class SAWGTestDRTIO(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl_sma_out")
        self.sawgs = [self.get_device("sawg"+str(i)) for i in range(16)]

    @kernel
    def run(self):
        core_log("waiting for DRTIO ready...")
        while not self.core.get_drtio_link_status(0):
            pass
        core_log("OK")

        self.core.reset()

        for sawg in self.sawgs:
                delay(1*ms)
                sawg.reset()

        for sawg in self.sawgs:
            delay(1*ms)
            sawg.amplitude1.set(.4)
            # Do not use a sub-multiple of oscilloscope sample rates.
            sawg.frequency0.set(9*MHz)

        while True:
            delay(0.5*ms)
            self.ttl_sma_out.pulse(0.5*ms)
