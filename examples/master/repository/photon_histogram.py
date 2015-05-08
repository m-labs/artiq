from artiq import *


class PhotonHistogram(Experiment, AutoDB):
    """Photon histogram"""

    class DBKeys:
        core = Device()
        dds_bus = Device()
        bd_dds = Device()
        bd_sw = Device()
        bdd_dds = Device()
        bdd_sw = Device()
        pmt = Device()

        nbins = Argument(100)
        repeats = Argument(100)

        cool_f = Parameter(230*MHz)
        detect_f = Parameter(220*MHz)
        detect_t = Parameter(100*us)

        ion_present = Parameter(True)

        hist = Result()
        total = Result()

    @kernel
    def program_cooling(self):
        self.dds_bus.batch_enter()
        self.bd_dds.set(200*MHz)
        self.bdd_dds.set(300*MHz)
        self.dds_bus.batch_exit()

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

        self.hist = hist
        self.total = total
        self.ion_present = total > 5*self.repeats


if __name__ == "__main__":
    from artiq.frontend.artiq_run import run
    run()
