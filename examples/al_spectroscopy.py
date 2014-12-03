from artiq import *


class AluminumSpectroscopy(AutoContext):
    mains_sync = Device("ttl_in")
    laser_cooling = Device("dds")
    spectroscopy = Device("dds")
    spectroscopy_b = Device("dac")
    state_detection = Device("dds")
    pmt = Device("ttl_in")
    spectroscopy_freq = Parameter(432*MHz)
    photon_limit_low = Parameter(10)
    photon_limit_high = Parameter(15)

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
