from artiq.experiment import *


class PulseRate(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("rsmap")

    @kernel
    def run(self):
        self.core.reset()

        dt = self.core.seconds_to_mu(300*ns)
        while True:
            for i in range(10000):
                try:
                    self.rsmap.pulse_mu(dt)
                    delay_mu(dt)
                except RTIOUnderflow:
                    dt += 1
                    self.core.break_realtime()
                    break
            else:
                print(self.core.mu_to_seconds(dt))
                return
