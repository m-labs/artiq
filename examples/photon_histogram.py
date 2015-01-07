from artiq import *


class PhotonHistogram(AutoContext):
    bd = Device("dds")
    bdd = Device("dds")
    pmt = Device("ttl_in")

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
    def run(self, nbins=100, repeats=100):
        hist = [0 for _ in range (nbins)]

        for i in range(repeats):
            n = self.cool_detect()
            if n >= nbins:
                n = nbins - 1
            hist[n] += 1

        print(hist)
