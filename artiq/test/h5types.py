import unittest

import h5py
import numpy as np

from artiq.master.worker_db import result_dict_to_hdf5


class TypesCase(unittest.TestCase):
    def test_types(self):
        d = {
            "int": 42,
            "float": 42.0,
            "string": "abcdef",

            "intlist": [1, 2, 3],
            "floatlist": [1.0, 2.0, 3.0]
        }

        for size in 8, 16, 32, 64:
            signed = getattr(np, "int" + str(size))
            unsigned = getattr(np, "uint" + str(size))
            d["i"+str(size)] = signed(42)
            d["u"+str(size)] = unsigned(42)
            d["i{}list".format(size)] = [signed(x) for x in range(3)]
            d["u{}list".format(size)] = [unsigned(x) for x in range(3)]
        for size in 16, 32, 64:
            ty = getattr(np, "float" + str(size))
            d["f"+str(size)] = ty(42)
            d["f{}list".format(size)] = [ty(x) for x in range(3)]

        with h5py.File("h5types.h5", "w") as f:
            result_dict_to_hdf5(f, d)
