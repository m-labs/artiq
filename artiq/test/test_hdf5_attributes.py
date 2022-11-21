import unittest
import io
import numpy as np
import h5py

from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase


class HDF5Attributes(EnvExperiment):
    """Archive data to HDF5 with attributes"""

    def run(self):
        # Attach attributes metadata to the HDF5 key
        # The key should exist in the resulting HDF5 file (archive=True).
        self.set_dataset("dummy", np.full(20, np.nan), broadcast=True, archive=True)
        self.set_dataset_metadata("dummy", "k1", "v1")
        self.set_dataset_metadata("dummy", "k2", "v2")


class TestHDF5Attributes(ExperimentCase):
    def setUp(self):
        super().setUp()
        self.exp = self.execute(HDF5Attributes)
        self.dump()

    def dump(self):
        self.bio = io.BytesIO()
        with h5py.File(self.bio, "w") as f:
            self.dataset_mgr.write_hdf5(f)

        self.bio.seek(0)
        self.h5file = h5py.File(self.bio, "r")
        self.datasets = self.h5file.get("datasets")

    def test_dataset_metadata(self):
        self.assertEqual(self.datasets["dummy"].attrs, {"k1": "v1", "k2": "v2"})
        self.assertTrue(np.all((self.datasets["dummy"], np.full(20, np.nan))))

    def test_write_none(self):
        with self.assertRaises(KeyError):
            self.exp.set_dataset_metadata(None, "test", "none")
        self.exp.set_dataset_metadata("dummy", None, "none")
        with self.assertRaises(TypeError):
            self.dump()

    def test_write_absent(self):
        with self.assertRaises(KeyError):
            self.exp.set_dataset_metadata("absent", "test", "absent")

    def test_rewrite(self):
        self.exp.set_dataset_metadata("dummy", "k2", "rewrite")
        self.dump()
        self.assertEqual(self.datasets["dummy"].attrs, {"k1": "v1", "k2": "rewrite"})

    def test_non_archive(self):
        self.exp.set_dataset("non_archive", np.full(30, np.nan), broadcast=True, archive=False)
        with self.assertRaises(KeyError):
            self.exp.set_dataset_metadata("non_archive", "k1", "v1")
