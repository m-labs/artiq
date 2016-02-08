from time import sleep

import numpy as np

from artiq import *


class Histograms(EnvExperiment):
    """Histograms demo"""
    def build(self):
        pass

    def run(self):
        nbins = 50
        npoints = 20

        bin_boundaries = np.linspace(-10, 30, nbins + 1)
        self.set_dataset("hd_bins", bin_boundaries,
                         broadcast=True, save=False)

        xs = np.empty(npoints)
        xs.fill(np.nan)
        xs = self.set_dataset("hd_xs", xs,
                              broadcast=True, save=False)

        counts = np.empty((npoints, nbins))
        counts = self.set_dataset("hd_counts", counts, 
                              broadcast=True, save=False)

        for i in range(npoints):
            histogram, _ = np.histogram(np.random.normal(i, size=1000),
                                        bin_boundaries)
            counts[i] = histogram
            xs[i] = i % 8
            sleep(0.3)
