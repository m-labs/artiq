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
        self.attr_argument("npoints", FreeValue(100))
        self.attr_argument("min_freq", FreeValue(1000))
        self.attr_argument("max_freq", FreeValue(2000))

        self.attr_argument("F0", FreeValue(1500))
        self.attr_argument("noise_amplitude", FreeValue(0.1))

        self.frequency = self.set_result("flopping_f_frequency", [], True)
        self.brightness = self.set_result("flopping_f_brightness", [], True)

        self.attr_device("scheduler")

    def run(self):
        for i in range(self.npoints):
            frequency = (self.max_freq-self.min_freq)*i/(self.npoints - 1) + self.min_freq
            brightness = model(frequency, self.F0) + self.noise_amplitude*random.random()
            self.frequency.append(frequency)
            self.brightness.append(brightness)
            time.sleep(0.1)
        self.scheduler.submit(self.scheduler.pipeline_name, self.scheduler.expid,
                              self.scheduler.priority, time.time() + 20, False)

    def analyze(self):
        popt, pcov = curve_fit(model_numpy,
                               self.frequency.read, self.brightness.read,
                               p0=[self.get_parameter("flopping_freq")])
        perr = np.sqrt(np.diag(pcov))
        if perr < 0.1:
            self.set_parameter("flopping_freq", float(popt))
