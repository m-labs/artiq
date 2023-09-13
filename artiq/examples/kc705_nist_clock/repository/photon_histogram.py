from numpy import int32

from artiq.experiment import *
from artiq.coredevice.core import Core
from artiq.coredevice.ad9914 import AD9914
from artiq.coredevice.ttl import TTLOut, TTLInOut


@nac3
class PhotonHistogram(EnvExperiment):
    """Photon histogram"""

    core: KernelInvariant[Core]
    bd_dds: KernelInvariant[AD9914]
    bd_sw: KernelInvariant[TTLOut]
    bdd_dds: KernelInvariant[AD9914]
    bdd_sw: KernelInvariant[TTLOut]
    pmt: KernelInvariant[TTLInOut]

    nbins: KernelInvariant[int32]
    repeats: KernelInvariant[int32]
    cool_f: KernelInvariant[float]
    detect_f: KernelInvariant[float]
    detect_t: KernelInvariant[float]

    def build(self):
        self.setattr_device("core")
        self.setattr_device("bd_dds")
        self.setattr_device("bd_sw")
        self.setattr_device("bdd_dds")
        self.setattr_device("bdd_sw")
        self.setattr_device("pmt")

        self.setattr_argument("nbins", NumberValue(100, precision=0, step=1))
        self.setattr_argument("repeats", NumberValue(100, precision=0, step=1))

        self.setattr_dataset("cool_f", 230*MHz)
        self.setattr_dataset("detect_f", 220*MHz)
        self.setattr_dataset("detect_t", 100*us)

    @kernel
    def program_cooling(self):
        delay_mu(-self.bd_dds.set_duration_mu)
        self.bd_dds.set(200.*MHz)
        delay_mu(self.bd_dds.set_duration_mu)
        self.bdd_dds.set(300.*MHz)

    @kernel
    def cool_detect(self) -> int32:
        with parallel:
            self.bd_sw.pulse(1.*ms)
            self.bdd_sw.pulse(1.*ms)

        self.bd_dds.set(self.cool_f)
        self.bd_sw.pulse(100.*us)

        self.bd_dds.set(self.detect_f)
        gate_end_mu = int64(0)
        with parallel:
            self.bd_sw.pulse(self.detect_t)
            gate_end_mu = self.pmt.gate_rising(self.detect_t)

        self.program_cooling()
        self.bd_sw.on()
        self.bdd_sw.on()

        return self.pmt.count(gate_end_mu)
    
    @rpc
    def report(self, hist: list[int32], ion_present: bool):
        self.set_dataset("cooling_photon_histogram", hist)
        self.set_dataset("ion_present", ion_present, broadcast=True)

    @kernel
    def run(self):
        self.core.reset()
        self.program_cooling()

        hist = [0 for _ in range(self.nbins)]
        total = 0

        for i in range(self.repeats):
            self.core.delay(0.5*ms)
            n = self.cool_detect()
            if n >= self.nbins:
                n = self.nbins - 1
            hist[n] += 1
            total += n

        self.report(hist, total > 5*self.repeats)
