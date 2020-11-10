r"""
The :mod:`math_fns` module lists math-related functions from NumPy recognized
by the ARTIQ compiler so host function objects can be :func:`match`\ ed to
the compiler type metadata describing their core device analogue.
"""

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
    "sqrt",
]] + [
    # numpy.rint() seems to (NumPy 1.19.0, Python 3.8.5, Linux x86_64)
    # implement round-to-even, but unfortunately, rust-lang/libm only
    # provides round(), which always rounds away from zero.
    #
    # As there is no equivalent of the latter in NumPy (nor any other
    # basic rounding function), expose round() as numpy.rint anyway,
    # even if the rounding modes don't match up, so there is some way
    # to do rounding on the core device. (numpy.round() has entirely
    # different semantics; it rounds to a configurable number of
    # decimals.)
    ("rint", "llvm.round.f64"),
]


#: float -> float numpy.* math functions lowered to runtime calls.
unary_fp_runtime_calls = [
    ("tan", "tan"),
    ("arcsin", "asin"),
    ("arccos", "acos"),
    ("arctan", "atan"),
    ("sinh", "sinh"),
    ("cosh", "cosh"),
    ("tanh", "tanh"),
    ("arcsinh", "asinh"),
    ("arccosh", "acosh"),
    ("arctanh", "atanh"),
    ("expm1", "expm1"),
    ("cbrt", "cbrt"),
]

#: (float, float) -> float numpy.* math functions lowered to runtime calls.
binary_fp_runtime_calls = [
    ("arctan2", "atan2"),
    ("copysign", "copysign"),
    ("fmax", "fmax"),
    ("fmin", "fmin"),
    # ("ldexp", "ldexp"),  # One argument is an int; would need a bit more plumbing.
    ("hypot", "hypot"),
    ("nextafter", "nextafter"),
]

#: Array handling builtins (special treatment due to allocations).
numpy_builtins = ["transpose"]


def fp_runtime_type(name, arity):
    args = [("arg{}".format(i), builtins.TFloat()) for i in range(arity)]
    return types.TExternalFunction(OrderedDict(args),
                                   builtins.TFloat(),
                                   name,
                                   # errno isn't observable from ARTIQ Python.
                                   flags={"nounwind", "nowrite"},
                                   broadcast_across_arrays=True)

numpy_map = {
    getattr(numpy, symbol): fp_runtime_type(mangle, arity=1)
    for symbol, mangle in (unary_fp_intrinsics + unary_fp_runtime_calls)
}
for symbol, mangle in binary_fp_runtime_calls:
    numpy_map[getattr(numpy, symbol)] = fp_runtime_type(mangle, arity=2)
for name in numpy_builtins:
    numpy_map[getattr(numpy, name)] = types.TBuiltinFunction("numpy." + name)


def match(obj):
    return numpy_map.get(obj, None)
