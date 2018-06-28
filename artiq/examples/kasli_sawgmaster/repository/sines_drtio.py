from artiq.experiment import *


class SAWGTestDRTIO(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.sawgs = [self.get_device("sawg"+str(i)) for i in range(16)]

    @kernel
    def run(self):
        while True:
            print("waiting for DRTIO ready...")
            while not (self.core.get_drtio_link_status(0) and
                       self.core.get_drtio_link_status(1)):
                pass
            print("OK")

            self.core.reset()

            for sawg in self.sawgs:
                delay(1*ms)
                sawg.reset()

            for sawg in self.sawgs:
                delay(1*ms)
                sawg.amplitude1.set(.4)
                # Do not use a sub-multiple of oscilloscope sample rates.
                sawg.frequency0.set(9*MHz)

            while self.core.get_drtio_link_status(0) and self.core.get_drtio_link_status(1):
                pass
