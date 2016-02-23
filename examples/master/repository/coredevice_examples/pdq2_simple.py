import numpy as np

from artiq.experiment import *
from artiq.wavesynth.coefficients import build_segment


class PDQ2Simple(EnvExperiment):
    """Set PDQ2 voltages."""
    def build(self):
        self.setattr_device("core")
        self.setattr_device("pmt")
        self.setattr_device("electrodes")

        # 1 device, 3 board each, 3 dacs each
        self.u = np.arange(4*3)[None, :, None]*.1

    def setup(self, offset):
        self.electrodes.disarm()
        self.load = self.electrodes.create_frame()
        segment = self.load.create_segment()
        for line in build_segment([100], self.u + offset):
            segment.add_line(**line)
        self.detect = self.electrodes.create_frame()
        segment = self.detect.create_segment()
        for line in build_segment([100], -self.u + offset):
            segment.add_line(**line)
        self.electrodes.arm()

    @kernel
    def one(self):
        self.load.advance()
        delay(1*ms)
        self.detect.advance()
        delay(1*ms)
        self.pmt.gate_rising(100*us)
        return self.pmt.count()

    def run(self):
        offsets = np.arange(0, 3)
        for o in offsets:
            self.setup(o)
            self.one()
