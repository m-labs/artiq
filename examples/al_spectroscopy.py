from artiq.language.units import *
from artiq.language.core import *


class AluminumSpectroscopy(AutoContext):
    parameters = "mains_sync laser_cooling spectroscopy spectroscopy_b state_detection pmt \
        spectroscopy_freq photon_limit_low photon_limit_high"

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


if __name__ == "__main__":
    from artiq.sim import devices as sd
    from artiq.sim import time

    exp = AluminumSpectroscopy(
        core=sd.Core(),
        mains_sync=sd.Input(name="mains_sync"),
        laser_cooling=sd.WaveOutput(name="laser_cooling"),
        spectroscopy=sd.WaveOutput(name="spectroscopy"),
        spectroscopy_b=sd.VoltageOutput(name="spectroscopy_b"),
        state_detection=sd.WaveOutput(name="state_detection"),
        pmt=sd.Input(name="pmt"),

        spectroscopy_freq=432*MHz,
        photon_limit_low=10,
        photon_limit_high=15
    )
    exp.run()
    print(time.manager.format_timeline())
