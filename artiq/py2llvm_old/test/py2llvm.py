import unittest
from pythonparser import parse, ast
import inspect
from fractions import Fraction
from ctypes import CFUNCTYPE, c_int, c_int32, c_int64, c_double
import struct

import llvmlite_or1k.binding as llvm

from artiq.language.core import int64
from artiq.py2llvm.infer_types import infer_function_types
from artiq.py2llvm import base_types, lists
from artiq.py2llvm.module import Module

def simplify_encode(a, b):
    f = Fraction(a, b)
    return f.numerator*1000 + f.denominator


def frac_arith_encode(op, a, b, c, d):
    if op == 0:
        f = Fraction(a, b) - Fraction(c, d)
    elif op == 1:
        f = Fraction(a, b) + Fraction(c, d)
    elif op == 2:
        f = Fraction(a, b) * Fraction(c, d)
    else:
        f = Fraction(a, b) / Fraction(c, d)
    return f.numerator*1000 + f.denominator


def frac_arith_encode_int(op, a, b, x):
    if op == 0:
        f = Fraction(a, b) - x
    elif op == 1:
        f = Fraction(a, b) + x
    elif op == 2:
        f = Fraction(a, b) * x
    else:
        f = Fraction(a, b) / x
    return f.numerator*1000 + f.denominator


def frac_arith_encode_int_rev(op, a, b, x):
    if op == 0:
        f = x - Fraction(a, b)
    elif op == 1:
        f = x + Fraction(a, b)
    elif op == 2:
        f = x * Fraction(a, b)
    else:
        f = x / Fraction(a, b)
    return f.numerator*1000 + f.denominator


def frac_arith_float(op, a, b, x):
    if op == 0:
        return Fraction(a, b) - x
    elif op == 1:
        return Fraction(a, b) + x
    elif op == 2:
        return Fraction(a, b) * x
    else:
        return Fraction(a, b) / x


def frac_arith_float_rev(op, a, b, x):
    if op == 0:
        return x - Fraction(a, b)
    elif op == 1:
        return x + Fraction(a, b)
    elif op == 2:
        return x * Fraction(a, b)
    else:
        return x / Fraction(a, b)


class CodeGenCase(unittest.TestCase):
    def test_frac_simplify(self):
        simplify_encode_c = CompiledFunction(
            simplify_encode, {"a": base_types.VInt(), "b": base_types.VInt()})
        for a in _test_range():
            for b in _test_range():
                self.assertEqual(
                    simplify_encode_c(a, b), simplify_encode(a, b))

    def _test_frac_arith(self, op):
        frac_arith_encode_c = CompiledFunction(
            frac_arith_encode, {
                "op": base_types.VInt(),
                "a": base_types.VInt(), "b": base_types.VInt(),
                "c": base_types.VInt(), "d": base_types.VInt()})
        for a in _test_range():
            for b in _test_range():
                for c in _test_range():
                    for d in _test_range():
                        self.assertEqual(
                            frac_arith_encode_c(op, a, b, c, d),
                            frac_arith_encode(op, a, b, c, d))

    def test_frac_add(self):
        self._test_frac_arith(0)

    def test_frac_sub(self):
        self._test_frac_arith(1)

    def test_frac_mul(self):
        self._test_frac_arith(2)

    def test_frac_div(self):
        self._test_frac_arith(3)

    def _test_frac_arith_int(self, op, rev):
        f = frac_arith_encode_int_rev if rev else frac_arith_encode_int
        f_c = CompiledFunction(f, {
            "op": base_types.VInt(),
            "a": base_types.VInt(), "b": base_types.VInt(),
            "x": base_types.VInt()})
        for a in _test_range():
            for b in _test_range():
                for x in _test_range():
                    self.assertEqual(
                        f_c(op, a, b, x),
                        f(op, a, b, x))

    def test_frac_add_int(self):
        self._test_frac_arith_int(0, False)
        self._test_frac_arith_int(0, True)

    def test_frac_sub_int(self):
        self._test_frac_arith_int(1, False)
        self._test_frac_arith_int(1, True)

    def test_frac_mul_int(self):
        self._test_frac_arith_int(2, False)
        self._test_frac_arith_int(2, True)

    def test_frac_div_int(self):
        self._test_frac_arith_int(3, False)
        self._test_frac_arith_int(3, True)

    def _test_frac_arith_float(self, op, rev):
        f = frac_arith_float_rev if rev else frac_arith_float
        f_c = CompiledFunction(f, {
            "op": base_types.VInt(),
            "a": base_types.VInt(), "b": base_types.VInt(),
            "x": base_types.VFloat()})
        for a in _test_range():
            for b in _test_range():
                for x in _test_range():
                    self.assertAlmostEqual(
                        f_c(op, a, b, x/2),
                        f(op, a, b, x/2))

    def test_frac_add_float(self):
        self._test_frac_arith_float(0, False)
        self._test_frac_arith_float(0, True)

    def test_frac_sub_float(self):
        self._test_frac_arith_float(1, False)
        self._test_frac_arith_float(1, True)

    def test_frac_mul_float(self):
        self._test_frac_arith_float(2, False)
        self._test_frac_arith_float(2, True)

    def test_frac_div_float(self):
        self._test_frac_arith_float(3, False)
        self._test_frac_arith_float(3, True)
