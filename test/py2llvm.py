import unittest
import ast
import inspect
from fractions import Fraction

from llvm import ee as le

from artiq.language.core import int64, array
from artiq.py2llvm.infer_types import infer_function_types
from artiq.py2llvm import base_types, arrays
from artiq.py2llvm.module import Module


def test_base_types(choice):
    a = 2          # promoted later to int64
    b = a + 1      # initially int32, becomes int64 after a is promoted
    c = b//2       # initially int32, becomes int64 after b is promoted
    d = 4          # stays int32
    x = int64(7)
    a += x         # promotes a to int64
    foo = True | True
    bar = None
    myf = 4.5
    myf2 = myf + x

    if choice and foo and not bar:
        return d
    elif myf2:
        return x + c
    else:
        return int64(8)


def _build_function_types(f):
    return infer_function_types(
        None, ast.parse(inspect.getsource(f)),
        dict())


class FunctionBaseTypesCase(unittest.TestCase):
    def setUp(self):
        self.ns = _build_function_types(test_base_types)

    def test_simple_types(self):
        self.assertIsInstance(self.ns["foo"], base_types.VBool)
        self.assertIsInstance(self.ns["bar"], base_types.VNone)
        self.assertIsInstance(self.ns["d"], base_types.VInt)
        self.assertEqual(self.ns["d"].nbits, 32)
        self.assertIsInstance(self.ns["x"], base_types.VInt)
        self.assertEqual(self.ns["x"].nbits, 64)
        self.assertIsInstance(self.ns["myf"], base_types.VFloat)
        self.assertIsInstance(self.ns["myf2"], base_types.VFloat)

    def test_promotion(self):
        for v in "abc":
            self.assertIsInstance(self.ns[v], base_types.VInt)
            self.assertEqual(self.ns[v].nbits, 64)

    def test_return(self):
        self.assertIsInstance(self.ns["return"], base_types.VInt)
        self.assertEqual(self.ns["return"].nbits, 64)


def test_array_types():
    a = array(0, 5)
    for i in range(2):
        a[i] = int64(8)
    return a


class FunctionArrayTypesCase(unittest.TestCase):
    def setUp(self):
        self.ns = _build_function_types(test_array_types)

    def test_array_types(self):
        self.assertIsInstance(self.ns["a"], arrays.VArray)
        self.assertIsInstance(self.ns["a"].el_init, base_types.VInt)
        self.assertEqual(self.ns["a"].el_init.nbits, 64)
        self.assertEqual(self.ns["a"].count, 5)
        self.assertIsInstance(self.ns["i"], base_types.VInt)
        self.assertEqual(self.ns["i"].nbits, 32)


class CompiledFunction:
    def __init__(self, function, param_types):
        module = Module()
        func_def = ast.parse(inspect.getsource(function)).body[0]
        self.function, self.retval = module.compile_function(
            func_def, param_types)
        self.argval = [param_types[arg.arg] for arg in func_def.args.args]
        self.ee = module.get_ee()

    def __call__(self, *args):
        args_llvm = []
        for av, a in zip(self.argval, args):
            if isinstance(av, base_types.VInt):
                al = le.GenericValue.int(av.get_llvm_type(), a)
            elif isinstance(av, base_types.VFloat):
                al = le.GenericValue.real(av.get_llvm_type(), a)
            else:
                raise NotImplementedError
            args_llvm.append(al)
        result = self.ee.run_function(self.function, args_llvm)
        if isinstance(self.retval, base_types.VBool):
            return bool(result.as_int())
        elif isinstance(self.retval, base_types.VInt):
            return result.as_int_signed()
        elif isinstance(self.retval, base_types.VFloat):
            return result.as_real(self.retval.get_llvm_type())
        else:
            raise NotImplementedError


def arith(op, a, b):
    if op == 1:
        return a + b
    elif op == 2:
        return a - b
    elif op == 3:
        return a * b
    else:
        return a / b


def is_prime(x):
    d = 2
    while d*d <= x:
        if not x % d:
            return False
        d += 1
    return True


def simplify_encode(a, b):
    f = Fraction(a, b)
    return f.numerator*1000 + f.denominator


def frac_arith_encode(op, a, b, c, d):
    if op == 1:
        f = Fraction(a, b) - Fraction(c, d)
    elif op == 2:
        f = Fraction(a, b) + Fraction(c, d)
    elif op == 3:
        f = Fraction(a, b) * Fraction(c, d)
    else:
        f = Fraction(a, b) / Fraction(c, d)
    return f.numerator*1000 + f.denominator


def frac_arith_encode_int(op, a, b, x):
    if op == 1:
        f = Fraction(a, b) - x
    elif op == 2:
        f = Fraction(a, b) + x
    elif op == 3:
        f = Fraction(a, b) * x
    else:
        f = Fraction(a, b) / x
    return f.numerator*1000 + f.denominator


def frac_arith_encode_int_rev(op, a, b, x):
    if op == 1:
        f = x - Fraction(a, b)
    elif op == 2:
        f = x + Fraction(a, b)
    elif op == 3:
        f = x * Fraction(a, b)
    else:
        f = x / Fraction(a, b)
    return f.numerator*1000 + f.denominator


def array_test():
    a = array(array(2, 5), 5)
    a[3][2] = 11
    a[4][1] = 42
    a[0][0] += 6

    acc = 0
    for i in range(5):
        for j in range(5):
            acc += a[i][j]
    return acc


def corner_cases():
    two = True + True - False
    three = two + True//True - False*True
    two_float = three - True/True
    one_float = two_float - (1.0 == bool(0.1))
    zero = int(one_float) + round(-0.6)
    eleven_float = zero + 5.5//0.5
    ten_float = eleven_float + round(Fraction(2, -3))
    return ten_float


def _test_range():
    for i in range(5, 10):
        yield i
        yield -i


class CodeGenCase(unittest.TestCase):
    def _test_float_arith(self, op):
        arith_c = CompiledFunction(arith, {
                "op": base_types.VInt(),
                "a": base_types.VFloat(), "b": base_types.VFloat()})
        for a in _test_range():
            for b in _test_range():
                self.assertEqual(arith_c(op, a/2, b/2), arith(op, a/2, b/2))

    def test_float_add(self):
        self._test_float_arith(0)

    def test_float_sub(self):
        self._test_float_arith(1)

    def test_float_mul(self):
        self._test_float_arith(2)

    def test_float_div(self):
        self._test_float_arith(3)

    def test_is_prime(self):
        is_prime_c = CompiledFunction(is_prime, {"x": base_types.VInt()})
        for i in range(200):
            self.assertEqual(is_prime_c(i), is_prime(i))

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

    def _test_frac_frac_arith_int(self, op, rev):
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
        self._test_frac_frac_arith_int(0, False)
        self._test_frac_frac_arith_int(0, True)

    def test_frac_sub_int(self):
        self._test_frac_frac_arith_int(1, False)
        self._test_frac_frac_arith_int(1, True)

    def test_frac_mul_int(self):
        self._test_frac_frac_arith_int(2, False)
        self._test_frac_frac_arith_int(2, True)

    def test_frac_div_int(self):
        self._test_frac_frac_arith_int(3, False)
        self._test_frac_frac_arith_int(3, True)

    def test_array(self):
        array_test_c = CompiledFunction(array_test, dict())
        self.assertEqual(array_test_c(), array_test())

    def test_corner_cases(self):
        corner_cases_c = CompiledFunction(corner_cases, dict())
        self.assertEqual(corner_cases_c(), corner_cases())
