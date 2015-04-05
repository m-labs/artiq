from artiq import *


class PhotonHistogram(Experiment, AutoDB):
    """Photon histogram"""

    class DBKeys:
        core = Device()
        bd = Device()
        bdd = Device()
        pmt = Device()

        nbins = Argument(100)
        repeats = Argument(100)

        cool_f = Parameter(230)
        detect_f = Parameter(220)
        detect_t = Parameter(100)

        ion_present = Parameter(True)

        hist = Result()
        total = Result()

    @kernel
    def cool_detect(self):
        with parallel:
            self.bd.pulse(200*MHz, 1*ms)
            self.bdd.pulse(300*MHz, 1*ms)
        self.bd.pulse(self.cool_f*MHz, 100*us)
        with parallel:
            self.bd.pulse(self.detect_f*MHz, self.detect_t*us)
            self.pmt.gate_rising(self.detect_t*us)
        self.bd.on(200*MHz)
        self.bdd.on(300*MHz)
        return self.pmt.count()

    @kernel
    def run(self):
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
