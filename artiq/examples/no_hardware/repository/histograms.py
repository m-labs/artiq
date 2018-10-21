from time import sleep

import numpy as np

from artiq.experiment import *


class Histograms(EnvExperiment):
    """Histograms demo"""
    def run(self):
        nbins = 50
        npoints = 20

        bin_boundaries = np.linspace(-10, 30, nbins + 1)
        self.set_dataset("hd_bins", bin_boundaries,
                         broadcast=True, archive=False)

        xs = np.empty(npoints)
        xs.fill(np.nan)
        self.set_dataset("hd_xs", xs,
                         broadcast=True, archive=False)

        self.set_dataset("hd_counts", np.empty((npoints, nbins)), 
                         broadcast=True, archive=False)

        for i in range(npoints):
            histogram, _ = np.histogram(np.random.normal(i, size=1000),
                                        bin_boundaries)
            self.mutate_dataset("hd_counts", i, histogram)
            self.mutate_dataset("hd_xs", i, i % 8)
            sleep(0.3)
