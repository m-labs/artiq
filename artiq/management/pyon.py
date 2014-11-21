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


def _encode_none(x):
    return "None"


def _encode_bool(x):
    if x:
        return "True"
    else:
        return "False"


def _encode_number(x):
    return str(x)


def _encode_str(x):
    return repr(x)


def _encode_tuple(x):
    if len(x) == 1:
        return "(" + encode(x[0]) + ", )"
    else:
        r = "("
        r += ", ".join([encode(item) for item in x])
        r += ")"
        return r


def _encode_list(x):
    r = "["
    r += ", ".join([encode(item) for item in x])
    r += "]"
    return r


def _encode_dict(x):
    r = "{"
    r += ", ".join([encode(k) + ": " + encode(v) for k, v in x.items()])
    r += "}"
    return r


def _encode_fraction(x):
    return "Fraction({}, {})".format(encode(x.numerator),
                                     encode(x.denominator))

def _encode_nparray(x):
    r = "nparray("
    r += encode(x.shape) + ", "
    r += encode(str(x.dtype)) + ", "
    r += encode(base64.b64encode(x).decode())
    r += ")"
    return r


_encode_map = {
    type(None): _encode_none,
    bool: _encode_bool,
    int: _encode_number,
    float: _encode_number,
    str: _encode_str,
    tuple: _encode_tuple,
    list: _encode_list,
    dict: _encode_dict,
    Fraction: _encode_fraction,
    numpy.ndarray: _encode_nparray
}


def encode(x):
    """Serializes a Python object and returns the corresponding string in
    Python syntax.

    """
    return _encode_map[type(x)](x)


def _nparray(shape, dtype, data):
    a = numpy.frombuffer(base64.b64decode(data), dtype=dtype)
    return a.reshape(shape)


_eval_dict = {
    "__builtins__": None,
    "Fraction": Fraction,
    "nparray": _nparray
}

def decode(s):
    """Parses a string in the Python syntax, reconstructs the corresponding
    object, and returns it.

    """
    return eval(s, _eval_dict, {})
