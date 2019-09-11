"""
This module provides serialization and deserialization functions for Python
objects. Its main features are:

* Human-readable format compatible with the Python syntax.
* Each object is serialized on a single line, with only ASCII characters.
* Supports all basic Python data structures: None, booleans, integers,
  floats, complex numbers, strings, tuples, lists, dictionaries.
* Those data types are accurately reconstructed (unlike JSON where e.g. tuples
  become lists, and dictionary keys are turned into strings).
* Supports Numpy arrays.

The main rationale for this new custom serializer (instead of using JSON) is
that JSON does not support Numpy and more generally cannot be extended with
other data types while keeping a concise syntax. Here we can use the Python
function call syntax to express special data types.
"""


from operator import itemgetter
import base64
from fractions import Fraction
from collections import OrderedDict
import os
import tempfile

import numpy


_encode_map = {
    type(None): "none",
    bool: "bool",
    int: "number",
    float: "number",
    complex: "number",
    str: "str",
    bytes: "bytes",
    tuple: "tuple",
    list: "list",
    set: "set",
    dict: "dict",
    slice: "slice",
    Fraction: "fraction",
    OrderedDict: "ordereddict",
    numpy.ndarray: "nparray"
}

_numpy_scalar = {
    "int8", "int16", "int32", "int64",
    "uint8", "uint16", "uint32", "uint64",
    "float16", "float32", "float64",
    "complex64", "complex128",
}


for _t in _numpy_scalar:
    _encode_map[getattr(numpy, _t)] = "npscalar"


_str_translation = {
    ord("\""): "\\\"",
    ord("\\"): "\\\\",
    ord("\n"): "\\n",
    ord("\r"): "\\r",
}


class _Encoder:
    def __init__(self, pretty):
        self.pretty = pretty
        self.indent_level = 0

    def indent(self):
        return "    "*self.indent_level

    def encode_none(self, x):
        return "null"

    def encode_bool(self, x):
        if x:
            return "true"
        else:
            return "false"

    def encode_number(self, x):
        return repr(x)

    def encode_str(self, x):
        # Do not use repr() for JSON compatibility.
        return "\"" + x.translate(_str_translation) + "\""

    def encode_bytes(self, x):
        return repr(x)

    def encode_tuple(self, x):
        if len(x) == 1:
            return "(" + self.encode(x[0]) + ", )"
        else:
            r = "("
            r += ", ".join([self.encode(item) for item in x])
            r += ")"
            return r

    def encode_list(self, x):
        r = "["
        r += ", ".join([self.encode(item) for item in x])
        r += "]"
        return r

    def encode_set(self, x):
        r = "{"
        r += ", ".join([self.encode(item) for item in x])
        r += "}"
        return r

    def encode_dict(self, x):
        if self.pretty and all(k.__class__ == str for k in x.keys()):
            items = lambda: sorted(x.items(), key=itemgetter(0))
        else:
            items = x.items

        r = "{"
        if not self.pretty or len(x) < 2:
            r += ", ".join([self.encode(k) + ": " + self.encode(v)
                           for k, v in items()])
        else:
            self.indent_level += 1
            r += "\n"
            first = True
            for k, v in items():
                if not first:
                    r += ",\n"
                first = False
                r += self.indent() + self.encode(k) + ": " + self.encode(v)
            r += "\n"  # no ','
            self.indent_level -= 1
            r += self.indent()
        r += "}"
        return r

    def encode_slice(self, x):
        return repr(x)

    def encode_fraction(self, x):
        return "Fraction({}, {})".format(self.encode(x.numerator),
                                         self.encode(x.denominator))

    def encode_ordereddict(self, x):
        return "OrderedDict(" + self.encode(list(x.items())) + ")"

    def encode_nparray(self, x):
        r = "nparray("
        r += self.encode(x.shape) + ", "
        r += self.encode(x.dtype.str) + ", "
        r += self.encode(base64.b64encode(x.data))
        r += ")"
        return r

    def encode_npscalar(self, x):
        r = "npscalar("
        r += self.encode(x.dtype.str) + ", "
        r += self.encode(base64.b64encode(x.data))
        r += ")"
        return r

    def encode(self, x):
        ty = _encode_map.get(type(x), None)
        if ty is None:
            raise TypeError("`{!r}` ({}) is not PYON serializable"
                            .format(x, type(x)))
        return getattr(self, "encode_" + ty)(x)


def encode(x, pretty=False):
    """Serializes a Python object and returns the corresponding string in
    Python syntax."""
    return _Encoder(pretty).encode(x)


def _nparray(shape, dtype, data):
    a = numpy.frombuffer(base64.b64decode(data), dtype=dtype)
    a = a.copy()
    return a.reshape(shape)


def _npscalar(ty, data):
    return numpy.frombuffer(base64.b64decode(data), dtype=ty)[0]


_eval_dict = {
    "__builtins__": {},

    "null": None,
    "false": False,
    "true": True,
    "inf": numpy.inf,
    "slice": slice,
    "nan": numpy.nan,

    "Fraction": Fraction,
    "OrderedDict": OrderedDict,
    "nparray": _nparray,
    "npscalar": _npscalar
}


def decode(s):
    """Parses a string in the Python syntax, reconstructs the corresponding
    object, and returns it."""
    return eval(s, _eval_dict, {})


def store_file(filename, x):
    """Encodes a Python object and writes it to the specified file."""
    contents = encode(x, True)
    directory = os.path.abspath(os.path.dirname(filename))
    with tempfile.NamedTemporaryFile("w", dir=directory, delete=False) as f:
        f.write(contents)
        f.write("\n")
        tmpname = f.name
    os.replace(tmpname, filename)


def load_file(filename):
    """Parses the specified file and returns the decoded Python object."""
    with open(filename, "r") as f:
        return decode(f.read())
