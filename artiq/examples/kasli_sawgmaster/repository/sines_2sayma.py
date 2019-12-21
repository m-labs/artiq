from artiq.experiment import *


class Sines2Sayma(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.sawgs = [self.get_device("sawg"+str(i)) for i in range(16)]

    @kernel
    def drtio_is_up(self):
        for i in range(5):
            if not self.core.get_rtio_destination_status(i):
                return False
        return True

    @kernel
    def run(self):
        while True:
            print("waiting for DRTIO ready...")
            while not self.drtio_is_up():
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

            while self.drtio_is_up():
                pass
