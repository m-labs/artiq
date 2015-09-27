from math import sqrt, cos, pi
import time
import random

import numpy as np
from scipy.optimize import curve_fit

from artiq import *


def model(x, F0):
    t = 0.02
    tpi = 0.03
    A = 80
    B = 40
    return A+(B-A)/2/(4*tpi**2*(x-F0)**2+1)*(1-cos(pi*t/tpi*sqrt(4*tpi**2*(x-F0)**2+1)))


def model_numpy(xdata, F0):
    r = np.zeros(len(xdata))
    for i, x in enumerate(xdata):
        r[i] = model(x, F0)
    return r


class FloppingF(EnvExperiment):
    """Flopping F simulation"""

    def build(self):
        self.attr_argument("frequency_scan", Scannable(
            default=LinearScan(1000, 2000, 100)))

        self.attr_argument("F0", NumberValue(1500, min=1000, max=2000))
        self.attr_argument("noise_amplitude", NumberValue(0.1, min=0, max=100,
                                                          step=0.01))

        self.attr_device("scheduler")

    def run(self):
        frequency = self.set_result("flopping_f_frequency", [],
                                    realtime=True, store=False)
        brightness = self.set_result("flopping_f_brightness", [],
                                     realtime=True)
        self.set_result("flopping_f_fit", [], realtime=True, store=False)

        for f in self.frequency_scan:
            m_brightness = model(f, self.F0) + self.noise_amplitude*random.random()
            frequency.append(f)
            brightness.append(m_brightness)
            time.sleep(0.1)
        self.scheduler.submit(self.scheduler.pipeline_name, self.scheduler.expid,
                              self.scheduler.priority, time.time() + 20, False)

    def analyze(self):
        # Use get_result so that analyze can be run stand-alone.
        frequency = self.get_result("flopping_f_frequency")
        brightness = self.get_result("flopping_f_brightness")
        popt, pcov = curve_fit(model_numpy,
                               frequency, brightness,
                               p0=[self.get_parameter("flopping_freq")])
        perr = np.sqrt(np.diag(pcov))
        if perr < 0.1:
            F0 = float(popt)
            self.set_parameter("flopping_freq", F0)
            self.set_result("flopping_f_fit",
                            [model(x, F0) for x in frequency],
                            realtime=True, store=False)
