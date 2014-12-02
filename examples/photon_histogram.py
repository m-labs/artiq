from artiq import *
from artiq.coredevice import comm_serial, core, dds, rtio


class PhotonHistogram(AutoContext):
    bd = Device("dds")
    bdd = Device("dds")
    pmt = Device("ttl_in")
    repeats = Parameter()
    nbins = Parameter()

    def report(self, i, n):
        print(i, n)

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
        hist = array(0, self.nbins)

        for i in range(self.repeats):
            n = self.cool_detect()
            if n >= self.nbins:
                n = self.nbins-1
            hist[n] += 1

        for i in range(self.nbins):
            self.report(i, hist[i])


def main():
    with comm_serial.Comm() as comm:
        coredev = core.Core(comm)
        exp = PhotonHistogram(
            core=coredev,
            bd=dds.DDS(core=coredev, dds_sysclk=1*GHz,
                       reg_channel=0, rtio_switch=2),
            bdd=dds.DDS(core=coredev, dds_sysclk=1*GHz,
                        reg_channel=1, rtio_switch=3),
            pmt=rtio.RTIOIn(core=coredev, channel=0),
            repeats=100,
            nbins=100
        )
        exp.run()

if __name__ == "__main__":
    main()
