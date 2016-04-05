import unittest

import h5py
import numpy as np


class TypesCase(unittest.TestCase):
    def test_types(self):
        d = {
            "bool": True,
            "int": 42,
            "float": 42.0,
            "string": "abcdef",
        }

        for size in 8, 16, 32, 64:
            for typ in "int", "uint":
                dt = getattr(np, typ + str(size))
                d[typ+str(size)] = dt(42)
                d["n"+typ+str(size)] = np.array(42, dt)
                d["m"+typ+str(size)] = np.array([[[[42]]]], dt)
        for size in 16, 32, 64:
            d["f"+str(size)] = getattr(np, "float" + str(size))(42)

        with h5py.File("h5types.h5", "w", "core", backing_store=False) as f:
            for k, v in d.items():
                f[k] = v
