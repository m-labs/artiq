from artiq.experiment import *


class PhotonHistogram(EnvExperiment):
    """Photon histogram"""

    def build(self):
        self.setattr_device("core")
        self.setattr_device("bd_dds")
        self.setattr_device("bd_sw")
        self.setattr_device("bdd_dds")
        self.setattr_device("bdd_sw")
        self.setattr_device("pmt")

        self.setattr_argument("nbins", NumberValue(100, ndecimals=0, step=1))
        self.setattr_argument("repeats", NumberValue(100, ndecimals=0, step=1))

        self.setattr_dataset("cool_f", 230*MHz)
        self.setattr_dataset("detect_f", 220*MHz)
        self.setattr_dataset("detect_t", 100*us)

    @kernel
    def program_cooling(self):
        delay_mu(-self.bd_dds.set_duration_mu)
        self.bd_dds.set(200*MHz)
        delay_mu(self.bd_dds.set_duration_mu)
        self.bdd_dds.set(300*MHz)

    @kernel
    def cool_detect(self):
        with parallel:
            self.bd_sw.pulse(1*ms)
            self.bdd_sw.pulse(1*ms)

        self.bd_dds.set(self.cool_f)
        self.bd_sw.pulse(100*us)

        self.bd_dds.set(self.detect_f)
        with parallel:
            self.bd_sw.pulse(self.detect_t)
            gate_end_mu = self.pmt.gate_rising(self.detect_t)

        self.program_cooling()
        self.bd_sw.on()
        self.bdd_sw.on()

        return self.pmt.count(gate_end_mu)

    @kernel
    def run(self):
        self.core.reset()
        self.program_cooling()

        hist = [0 for _ in range(self.nbins)]
        total = 0

        for i in range(self.repeats):
            delay(0.5*ms)
            n = self.cool_detect()
            if n >= self.nbins:
                n = self.nbins - 1
            hist[n] += 1
            total += n

        self.set_dataset("cooling_photon_histogram", hist)
        self.set_dataset("ion_present", total > 5*self.repeats,
                         broadcast=True)


if __name__ == "__main__":
    from artiq.frontend.artiq_run import run
    run()
