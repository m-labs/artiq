from artiq import *


class PhotonHistogram(AutoDB):
    __artiq_unit__ = "Photon histogram"

    class DBKeys:
        bd = Device()
        bdd = Device()
        pmt = Device()

        nbins = Argument(100)
        repeats = Argument(100)

    @kernel
    def cool_detect(self):
        with parallel:
            self.bd.pulse(200*MHz, 1*ms)
            self.bdd.pulse(300*MHz, 1*ms)
        self.bd.pulse(210*MHz, 100*us)
        with parallel:
            self.bd.pulse(220*MHz, 100*us)
            self.pmt.gate_rising(100*us)
        self.bd.on(200*MHz)
        self.bdd.on(300*MHz)
        return self.pmt.count()

    @kernel
    def run(self):
        hist = [0 for _ in range(self.nbins)]

        for i in range(self.repeats):
            n = self.cool_detect()
            if n >= self.nbins:
                n = self.nbins - 1
            hist[n] += 1

        print(hist)
