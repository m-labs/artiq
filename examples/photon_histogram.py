from artiq import *


class PhotonHistogram(AutoContext):
    bd = Device("dds")
    bdd = Device("dds")
    pmt = Device("ttl_in")
    repeats = Parameter(100)
    nbins = Parameter(100)

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
        hist = [0 for _ in range (self.nbins)]

        for i in range(self.repeats):
            n = self.cool_detect()
            if n >= self.nbins:
                n = self.nbins-1
            hist[n] += 1

        for i in range(self.nbins):
            print(i, hist[i])
