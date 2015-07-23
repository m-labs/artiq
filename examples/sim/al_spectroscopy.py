from artiq import *


class AluminumSpectroscopy(EnvExperiment):
    """Aluminum spectroscopy (simulation)"""

    def build(self):
        self.attr_device("core")
        self.attr_device("mains_sync")
        self.attr_device("laser_cooling")
        self.attr_device("spectroscopy")
        self.attr_device("spectroscopy_b")
        self.attr_device("state_detection")
        self.attr_device("pmt")
        self.attr_parameter("spectroscopy_freq", 432*MHz)
        self.attr_argument("photon_limit_low", FreeValue(10))
        self.attr_argument("photon_limit_high", FreeValue(15))

    @kernel
    def run(self):
        state_0_count = 0
        for count in range(100):
            self.mains_sync.wait_edge()
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
                    photon_count = self.pmt.count_gate(10*us)
                if (photon_count < self.photon_limit_low
                        or photon_count > self.photon_limit_high):
                    break
            if photon_count < self.photon_limit_low:
                state_0_count += 1
        return state_0_count
