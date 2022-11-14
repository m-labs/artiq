import unittest
import numpy as np

from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase


class HDF5Attributes(EnvExperiment):
    """Archive data to HDF5 with attributes"""

    def run(self):
        # Attach attributes to the HDF5 group `datasets`
        self.set_dataset_metadata(None, {
            "arr": np.array([1, 2, 3]),
            "description": "demo",
        })

        # `archive=True` is required in order to
        # attach attributes to HDF5 datasets
        self.set_dataset("dummy", np.full(20, np.nan), broadcast=True, archive=True)
        self.set_dataset_metadata("dummy", {"k1": "v1", "k2": "v2"})

        self.set_dataset("no_archive", np.full(30, np.nan), broadcast=False, archive=False)
        self.set_dataset_metadata("no_archive", {"na_k": "na_v"})

        self.set_dataset_metadata("nothing", {"k": "v"})
        self.set_dataset_metadata(None, {"general": "metadata"})


class TestHDF5Attributes(ExperimentCase):
    def setUp(self):
        super().setUp()
        self.exp = self.execute(HDF5Attributes)

    def test_dataset_metadata(self):
        self.assertNotEqual(self.dataset_mgr, None)
        self.assertEqual(self.dataset_mgr.hdf5_attributes["datasets/dummy"], {"k1": "v1", "k2": "v2"})
        self.assertTrue(np.all((self.dataset_mgr.local["dummy"], np.full(20, np.nan))))

    def test_absent_key_metadata(self):
        self.assertEqual(self.dataset_mgr.hdf5_attributes["datasets/nothing"], {"k": "v"})

    def test_none_key_metadata(self):
        self.assertEqual(self.dataset_mgr.hdf5_attributes["datasets"], {"general": "metadata"})

    def test_no_archive(self):
        self.assertEqual(self.dataset_mgr.hdf5_attributes["datasets/no_archive"], {"na_k": "na_v"})
        with self.assertRaises(KeyError):
            _ = self.dataset_mgr.local["no_archive"]
