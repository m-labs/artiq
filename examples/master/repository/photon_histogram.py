from artiq import *


class PhotonHistogram(EnvExperiment):
    """Photon histogram"""

    def build(self):
        self.attr_device("core")
        self.attr_device("dds_bus")
        self.attr_device("bd_dds")
        self.attr_device("bd_sw")
        self.attr_device("bdd_dds")
        self.attr_device("bdd_sw")
        self.attr_device("pmt")

        self.attr_argument("nbins", FreeValue(100))
        self.attr_argument("repeats", FreeValue(100))

        self.attr_parameter("cool_f", 230*MHz)
        self.attr_parameter("detect_f", 220*MHz)
        self.attr_parameter("detect_t", 100*us)

    @kernel
    def program_cooling(self):
        with self.dds_bus.batch:
            self.bd_dds.set(200*MHz)
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
            self.pmt.gate_rising(self.detect_t)

        self.program_cooling()
        self.bd_sw.on()
        self.bdd_sw.on()

        return self.pmt.count()

    @kernel
    def run(self):
        self.program_cooling()

        hist = [0 for _ in range(self.nbins)]
        total = 0

        for i in range(self.repeats):
            n = self.cool_detect()
            if n >= self.nbins:
                n = self.nbins - 1
            hist[n] += 1
            total += n

        self.set_result("cooling_photon_histogram", hist)
        self.set_parameter("ion_present", total > 5*self.repeats)


if __name__ == "__main__":
    from artiq.frontend.artiq_run import run
    run()
