import unittest

import h5py
import numpy as np

from artiq.master.worker_db import result_dict_to_hdf5


class TypesCase(unittest.TestCase):
    def test_types(self):
        d = {
            "bool": True,
            "int": 42,
            "float": 42.0,
            "string": "abcdef",
        }

        for size in 8, 16, 32, 64:
            d["i"+str(size)] = getattr(np, "int" + str(size))(42)
            d["u"+str(size)] = getattr(np, "uint" + str(size))(42)
        for size in 16, 32, 64:
            d["f"+str(size)] = getattr(np, "float" + str(size))(42)

        with h5py.File("h5types.h5", "w", "core", backing_store=False) as f:
            result_dict_to_hdf5(f, d)
