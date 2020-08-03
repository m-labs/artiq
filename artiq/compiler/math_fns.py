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

#: Array handling builtins (special treatment due to allocations).
numpy_builtins = ["transpose"]


def unary_fp_type(name):
    return types.TExternalFunction(OrderedDict([("arg", builtins.TFloat())]),
                                   builtins.TFloat(),
                                   name,
                                   # errno isn't observable from ARTIQ Python.
                                   flags={"nounwind", "nowrite"},
                                   broadcast_across_arrays=True)


numpy_map = {
    getattr(numpy, symbol): unary_fp_type(mangle)
    for symbol, mangle in (unary_fp_intrinsics + unary_fp_runtime_calls)
}
for name in numpy_builtins:
    numpy_map[getattr(numpy, name)] = types.TBuiltinFunction("numpy." + name)


def match(obj):
    return numpy_map.get(obj, None)
