from artiq.language.core import *
from artiq.language.units import *
from artiq.devices import corecom_serial, core, dds_core, rtio_core


class PhotonHistogram(AutoContext):
    parameters = "bd bdd pmt repeats nbins"

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
            self.pmt.count_rising(100*us)
        self.bd.on(200*MHz)
        self.bdd.on(300*MHz)
        return self.pmt.sync()

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


if __name__ == "__main__":
    with corecom_serial.CoreCom() as com:
        coredev = core.Core(com)
        exp = PhotonHistogram(
            core=coredev,
            bd=dds_core.DDS(core=coredev, dds_sysclk=1*GHz,
                            reg_channel=0, rtio_channel=1),
            bdd=dds_core.DDS(core=coredev, dds_sysclk=1*GHz,
                             reg_channel=1, rtio_channel=2),
            pmt=rtio_core.RTIOCounter(core=coredev, channel=0),
            repeats=100,
            nbins=100
        )
        exp.run()
