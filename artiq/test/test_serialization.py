import unittest
import json
from fractions import Fraction

import numpy as np

from artiq.protocols import pyon


_pyon_test_object = {
    (1, 2): [(3, 4.2), (2, )],
    "slice": slice(3),
    Fraction(3, 4): np.linspace(5, 10, 1),
    "set": {"testing", "sets"},
    "a": np.int8(9), "b": np.int16(-98), "c": np.int32(42), "d": np.int64(-5),
    "e": np.uint8(8), "f": np.uint16(5), "g": np.uint32(4), "h": np.uint64(9),
    "x": np.float16(9.0), "y": np.float32(9.0), "z": np.float64(9.0),
    1j: 1-9j,
    "q": np.complex128(1j),
}


class PYON(unittest.TestCase):
    def test_encdec(self):
        for enc in pyon.encode, lambda x: pyon.encode(x, True):
            with self.subTest(enc=enc):
                self.assertEqual(pyon.decode(enc(_pyon_test_object)),
                                 _pyon_test_object)

    def test_encdec_array(self):
        orig = {k: (np.array(v), np.array([v]))
                for k, v in _pyon_test_object.items()
                if np.isscalar(v)}
        for enc in pyon.encode, lambda x: pyon.encode(x, True):
            result = pyon.decode(enc(orig))
            for k in orig:
                with self.subTest(enc=enc, k=k, v=orig[k]):
                    np.testing.assert_equal(result[k], orig[k])


_json_test_object = {
    "a": "b",
    "x": [1, 2, {}],
    "foo\nbaz\\qux\"\r2": ["bar", 1.2, {"x": "y"}],
    "bar": [True, False, None]
}


class JSONPYON(unittest.TestCase):
    def test_encdec(self):
        for enc in pyon.encode, lambda x: pyon.encode(x, True), json.dumps:
            for dec in pyon.decode, json.loads:
                self.assertEqual(dec(enc(_json_test_object)),
                                 _json_test_object)
