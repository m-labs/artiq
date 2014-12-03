"""
This module provide serialization and deserialization functions for Python
objects. Its main features are:

* Human-readable format compatible with the Python syntax.
* Each object is serialized on a single line, with only ASCII characters.
* Supports all basic Python data structures: None, booleans, integers,
  floats, strings, tuples, lists, dictionaries.
* Those data types are accurately reconstructed (unlike JSON where e.g. tuples
  become lists, and dictionary keys are turned into strings).
* Supports Numpy arrays.

The main rationale for this new custom serializer (instead of using JSON) is
that JSON does not support Numpy and more generally cannot be extended with
other data types while keeping a concise syntax. Here we can use the Python
function call syntax to mark special data types.

"""


import base64
from fractions import Fraction

import numpy


_encode_map = {
    type(None): "none",
    bool: "bool",
    int: "number",
    float: "number",
    str: "str",
    tuple: "tuple",
    list: "list",
    dict: "dict",
    Fraction: "fraction",
    numpy.ndarray: "nparray"
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
        return str(x)

    def encode_str(self, x):
        tt = {ord("\""): "\\\"", ord("\\"): "\\\\", ord("\n"): "\\n"}
        return "\"" + x.translate(tt) + "\""

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

    def encode_dict(self, x):
        r = "{"
        if not self.pretty or len(x) < 2:
            r += ", ".join([self.encode(k) + ": " + self.encode(v)
                           for k, v in x.items()])
        else:
            self.indent_level += 1
            r += "\n"
            first = True
            for k, v in x.items():
                if not first:
                    r += ",\n"
                first = False
                r += self.indent() + self.encode(k) + ": " + self.encode(v)
            r += "\n"  # no ','
            self.indent_level -= 1
            r += self.indent()
        r += "}"
        return r

    def encode_fraction(self, x):
        return "Fraction({}, {})".format(encode(x.numerator),
                                         encode(x.denominator))

    def encode_nparray(self, x):
        r = "nparray("
        r += encode(x.shape) + ", "
        r += encode(str(x.dtype)) + ", "
        r += encode(base64.b64encode(x).decode())
        r += ")"
        return r

    def encode(self, x):
        return getattr(self, "encode_" + _encode_map[type(x)])(x)


def encode(x, pretty=False):
    """Serializes a Python object and returns the corresponding string in
    Python syntax.

    """
    return _Encoder(pretty).encode(x)


def _nparray(shape, dtype, data):
    a = numpy.frombuffer(base64.b64decode(data), dtype=dtype)
    return a.reshape(shape)


_eval_dict = {
    "__builtins__": None,

    "null": None,
    "false": False,
    "true": True,

    "Fraction": Fraction,
    "nparray": _nparray
}

def decode(s):
    """Parses a string in the Python syntax, reconstructs the corresponding
    object, and returns it.

    """
    return eval(s, _eval_dict, {})


def store_file(filename, x):
    """Encodes a Python object and writes it to the specified file.

    """
    with open(filename, "w") as f:
        f.write(encode(x, True))


def load_file(filename):
    """Parses the specified file and returns the decoded Python object.

    """
    with open(filename, "r") as f:
        return decode(f.read())
