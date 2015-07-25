import unittest
import json
from fractions import Fraction

import numpy as np

from artiq.protocols import pyon


_pyon_test_object = {
    (1, 2): [(3, 4.2), (2, )],
    Fraction(3, 4): np.linspace(5, 10, 1),
}


class PYON(unittest.TestCase):
    def test_encdec(self):
        for enc in pyon.encode, lambda x: pyon.encode(x, True):
            self.assertEqual(pyon.decode(enc(_pyon_test_object)),
                             _pyon_test_object)


_json_test_object = {
    "a": "b",
    "x": [1, 2, {}],
    "foo\nbaz\\qux\"": ["bar", 1.2, {"x": "y"}],
    "bar": [True, False, None]
}


class JSONPYON(unittest.TestCase):
    def test_encdec(self):
        for enc in pyon.encode, lambda x: pyon.encode(x, True), json.dumps:
            for dec in pyon.decode, json.loads:
                self.assertEqual(dec(enc(_json_test_object)),
                                 _json_test_object)
