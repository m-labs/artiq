from collections import OrderedDict
import numpy
from . import builtins, types

#: float -> float numpy.* math functions for which llvm.* intrinsics exist.
unary_fp_intrinsics = [(name, "llvm." + name + ".f64") for name in [
    "sin",
    "cos",
    "exp",
    "exp2",
    "log",
    "log10",
    "log2",
    "fabs",
    "floor",
    "ceil",
    "trunc",
    "rint",
]]

#: float -> float numpy.* math functions lowered to runtime calls.
unary_fp_runtime_calls = [
    ("tan", "tan"),
    ("arcsin", "asin"),
    ("arccos", "acos"),
    ("arctan", "atan"),
]


def unary_fp_type(name):
    return types.TExternalFunction(OrderedDict([("arg", builtins.TFloat())]),
                                   builtins.TFloat(), name)


numpy_map = {
    getattr(numpy, symbol): unary_fp_type(mangle)
    for symbol, mangle in (unary_fp_intrinsics + unary_fp_runtime_calls)
}


def match(obj):
    return numpy_map.get(obj, None)
