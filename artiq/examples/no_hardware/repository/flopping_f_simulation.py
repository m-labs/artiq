import time
import random

import numpy as np
from scipy.optimize import curve_fit

from artiq.experiment import *


def model(x, F0):
    t = 0.02
    tpi = 0.03
    A = 80
    B = 40
    return A + (B - A)/2/(4*tpi**2*(x - F0)**2+1)*(
        1 - np.cos(np.pi*t/tpi*np.sqrt(4*tpi**2*(x - F0)**2 + 1))
    )


class FloppingF(EnvExperiment):
    """Flopping F simulation"""

    def build(self):
        self.setattr_argument("frequency_scan", Scannable(
            default=RangeScan(1000, 2000, 100)))

        self.setattr_argument("F0", NumberValue(1500, min=1000, max=2000))
        self.setattr_argument("noise_amplitude", NumberValue(
            0.1, min=0, max=100, step=0.01))

        self.setattr_device("scheduler")
        self.setattr_device("ccb")

    def run(self):
        l = len(self.frequency_scan)
        self.set_dataset("flopping_f_frequency",
                         np.full(l, np.nan),
                         broadcast=True, archive=False)
        self.set_dataset("flopping_f_brightness",
                         np.full(l, np.nan),
                         broadcast=True)
        self.set_dataset("flopping_f_fit", np.full(l, np.nan),
                         broadcast=True, archive=False)

        self.ccb.issue("create_applet", "flopping_f",
           "${artiq_applet}plot_xy "
           "flopping_f_brightness --x flopping_f_frequency "
           "--fit flopping_f_fit")

        for i, f in enumerate(self.frequency_scan):
            m_brightness = model(f, self.F0) + self.noise_amplitude*random.random()
            self.mutate_dataset("flopping_f_frequency", i, f)
            self.mutate_dataset("flopping_f_brightness", i, m_brightness)
            time.sleep(0.1)
        self.scheduler.submit(due_date=time.time() + 20)

    def analyze(self):
        # Use get_dataset so that analyze can be run stand-alone.
        brightness = self.get_dataset("flopping_f_brightness")
        try:
            frequency = self.get_dataset("flopping_f_frequency", archive=False)
        except KeyError:
            # Since flopping_f_frequency is not saved, it is missing if
            # analyze() is run on HDF5 data. But assuming that the arguments
            # have been loaded from that same HDF5 file, we can reconstruct it.
            frequency = np.fromiter(self.frequency_scan, np.float)
            assert frequency.shape == brightness.shape
            self.set_dataset("flopping_f_frequency", frequency,
                             broadcast=True, archive=False)
        popt, pcov = curve_fit(model, frequency, brightness,
                               p0=[self.get_dataset("flopping_freq", 1500.0,
                                                    archive=False)])
        perr = np.sqrt(np.diag(pcov))
        if perr < 0.1:
            F0 = float(popt)
            self.set_dataset("flopping_freq", F0, persist=True, archive=False)
            self.set_dataset("flopping_f_fit",
                             np.array([model(x, F0) for x in frequency]),
                             broadcast=True, archive=False)
