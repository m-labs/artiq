import numpy as np

from artiq.experiment import *


class HDF5Attributes(EnvExperiment):
    """Archive data to HDF5 with attributes"""
    def run(self):
        # Attach attributes to the HDF5 group `datasets`
        self.set_dataset_metadata(None, {
            "arr": np.array([1, 2, 3]),
            "description": "demo",
        })

        dummy = np.empty(20)
        dummy.fill(np.nan)
        # `archive=True` is required in order to
        # attach attributes to HDF5 datasets
        self.set_dataset("dummy", dummy,
                         broadcast=True, archive=True)
        self.set_dataset_metadata("dummy", {"k1": "v1", "k2": "v2"})

        # Attach metadata to an absent key is no-op
        self.set_dataset_metadata("nothing", {"no": "op"})
