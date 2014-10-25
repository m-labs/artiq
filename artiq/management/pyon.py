import base64

import numpy


def _encode_none(x):
    return "None"


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


def _encode_nparray(x):
    r = "nparray("
    r += encode(x.shape) + ", "
    r += encode(str(x.dtype)) + ", "
    r += encode(base64.b64encode(x).decode())
    r += ")"
    return r


_encode_map = {
    type(None): _encode_none,
    int: _encode_number,
    float: _encode_number,
    str: _encode_str,
    tuple: _encode_tuple,
    list: _encode_list,
    dict: _encode_dict,
    numpy.ndarray: _encode_nparray
}


def encode(x):
    return _encode_map[type(x)](x)


def _nparray(shape, dtype, data):
    a = numpy.frombuffer(base64.b64decode(data), dtype=dtype)
    return a.reshape(shape)


def decode(s):
    return eval(s, {"__builtins__": None, "nparray": _nparray}, {})
