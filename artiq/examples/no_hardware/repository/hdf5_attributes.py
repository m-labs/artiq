import numpy as np

from artiq.experiment import *


class HDF5Attributes(EnvExperiment):
    """Archive data to HDF5 with attributes"""

    def run(self):
        dummy = np.empty(20)
        dummy.fill(np.nan)
        self.set_dataset("dummy", dummy,
                         broadcast=True, archive=True)
        self.set_dataset_metadata("dummy", "k1", "v1")
        self.set_dataset_metadata("dummy", "k2", "v2")
