from artiq.experiment import *


class AluminumSpectroscopy(EnvExperiment):
    """Aluminum spectroscopy (simulation)"""

    def build(self):
        self.setattr_device("core")
        self.setattr_device("mains_sync")
        self.setattr_device("laser_cooling")
        self.setattr_device("spectroscopy")
        self.setattr_device("spectroscopy_b")
        self.setattr_device("state_detection")
        self.setattr_device("pmt")
        self.setattr_dataset("spectroscopy_freq", 432*MHz)
        self.setattr_argument("photon_limit_low", NumberValue(10))
        self.setattr_argument("photon_limit_high", NumberValue(15))

    @kernel
    def run(self):
        state_0_count = 0
        for count in range(100):
            self.mains_sync.gate_rising(1*s/60)
            at_mu(self.mains_sync.timestamp_mu(now_mu()) + 100*us)
            delay(10*us)
            self.laser_cooling.pulse(100*MHz, 100*us)
            delay(5*us)
            with parallel:
                self.spectroscopy.pulse(self.spectroscopy_freq, 100*us)
                with sequential:
                    delay(50*us)
                    self.spectroscopy_b.set(200)
            delay(5*us)
            while True:
                delay(5*us)
                with parallel:
                    self.state_detection.pulse(100*MHz, 10*us)
                    photon_count = self.pmt.count(self.pmt.gate_rising(10*us))
                if (photon_count < self.photon_limit_low or
                        photon_count > self.photon_limit_high):
                    break
            if photon_count < self.photon_limit_low:
                state_0_count += 1
        print(state_0_count)
