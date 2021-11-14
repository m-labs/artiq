from artiq.experiment import *
import numpy
import scipy.special
from artiq.test.hardware_testbench import ExperimentCase
from artiq.compiler.targets import CortexA9Target
from artiq.compiler import math_fns


class _RunOnDevice(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    @kernel
    def run_on_kernel_unary(self, a, callback, numpy, scipy):
        self.run(a, callback, numpy, scipy)

    @kernel
    def run_on_kernel_binary(self, a, b, callback, numpy, scipy):
        self.run(a, b, callback, numpy, scipy)


# Binary operations supported for scalars and arrays of any dimension, including
# broadcasting.
ELEM_WISE_BINOPS = ["+", "*", "//", "%", "**", "-", "/"]


class CompareHostDeviceTest(ExperimentCase):
    def _test_binop(self, op, a, b):
        exp = self.create(_RunOnDevice)
        exp.run = kernel_from_string(["a", "b", "callback", "numpy", "scipy"],
                                     "callback(" + op + ")",
                                     decorator=portable)
        checked = False

        def with_host_result(host):
            def with_both_results(device):
                nonlocal checked
                checked = True
                self.assertTrue(
                    numpy.allclose(host, device, equal_nan=True),
                    "Discrepancy in binop test for '{}': Expexcted ({}, {}) -> {}, got {}"
                    .format(op, a, b, host, device))

            exp.run_on_kernel_binary(a, b, with_both_results, numpy, scipy)

        exp.run(a, b, with_host_result, numpy, scipy)
        self.assertTrue(checked, "Test did not run")

    def _test_unaryop(self, op, a):
        exp = self.create(_RunOnDevice)
        exp.run = kernel_from_string(["a", "callback", "numpy", "scipy"],
                                     "callback(" + op + ")",
                                     decorator=portable)
        checked = False

        def with_host_result(host):
            def with_both_results(device):
                nonlocal checked
                checked = True
                self.assertTrue(
                    numpy.allclose(host, device, equal_nan=True),
                    "Discrepancy in unaryop test for '{}': Expexcted {} -> {}, got {}"
                    .format(op, a, host, device))

            exp.run_on_kernel_unary(a, with_both_results, numpy, scipy)

        exp.run(a, with_host_result, numpy, scipy)
        self.assertTrue(checked, "Test did not run")

    def test_scalar_scalar_binops(self):
        # Some arbitrarily chosen arguments of different types. Could be turned into
        # randomised tests instead.
        # TODO: Provoke overflows, division by zero, etc., and compare results.
        args = [(typ(a), typ(b)) for a, b in [(0, 1), (3, 2), (11, 6)]
                for typ in [numpy.int32, numpy.int64, numpy.float64]]
        for op in ELEM_WISE_BINOPS:
            for arg in args:
                self._test_binop("a" + op + "b", *arg)

    def test_scalar_matrix_binops(self):
        for typ in [numpy.int32, numpy.int64, numpy.float64]:
            scalar = typ(3)
            matrix = numpy.array([[4, 5, 6], [7, 8, 9]], dtype=typ)
            for op in ELEM_WISE_BINOPS:
                code = "a" + op + "b"
                self._test_binop(code, scalar, matrix)
                self._test_binop(code, matrix, scalar)
                self._test_binop(code, matrix, matrix)

    def test_matrix_mult(self):
        for typ in [numpy.int32, numpy.int64, numpy.float64]:
            mat_a = numpy.array([[1, 2, 3], [4, 5, 6]], dtype=typ)
            mat_b = numpy.array([[7, 8], [9, 10], [11, 12]], dtype=typ)
            self._test_binop("a @ b", mat_a, mat_b)

    def test_unary_math_fns(self):
        names = [
            a for a, _ in math_fns.unary_fp_intrinsics + math_fns.unary_fp_runtime_calls
        ]
        exp = self.create(_RunOnDevice)
        if exp.core.target_cls != CortexA9Target:
            names.remove("exp2")
            names.remove("log2")
            names.remove("trunc")
        for name in names:
            op = "numpy.{}(a)".format(name)
            # Avoid 0.5, as numpy.rint's rounding mode currently doesn't match.
            self._test_unaryop(op, 0.51)
            self._test_unaryop(op, numpy.array([[0.3, 0.4], [0.51, 0.6]]))

    def test_unary_scipy_fns(self):
        names = [name for name, _ in math_fns.scipy_special_unary_runtime_calls]
        if self.create(_RunOnDevice).core.target_cls != CortexA9Target:
            names.remove("gamma")
        for name in names:
            op = "scipy.special.{}(a)".format(name)
            self._test_unaryop(op, 0.5)
            self._test_unaryop(op, numpy.array([[0.3, 0.4], [0.5, 0.6]]))

    def test_binary_math_fns(self):
        names = [name for name, _ in math_fns.binary_fp_runtime_calls]
        exp = self.create(_RunOnDevice)
        if exp.core.target_cls != CortexA9Target:
            names.remove("fmax")
            names.remove("fmin")
        for name in names:
            code = "numpy.{}(a, b)".format(name)
            # Avoid 0.5, as numpy.rint's rounding mode currently doesn't match.
            self._test_binop(code, 1.0, 2.0)
            self._test_binop(code, 1.0, numpy.array([2.0, 3.0]))
            self._test_binop(code, numpy.array([1.0, 2.0]), 3.0)
            self._test_binop(code, numpy.array([1.0, 2.0]), numpy.array([3.0, 4.0]))


class _MatrixMult(EnvExperiment):
    """Regression test for GitHub #1578 (ICE when mixing different matrix multiplication
    types in one kernel).
    """
    def build(self):
        self.setattr_device("core")
        self.imat = numpy.arange(4, dtype=numpy.int64).reshape((2, 2))
        self.fmat = numpy.arange(4, dtype=numpy.float64).reshape((2, 2))

    @kernel
    def run(self):
        self.verify(self.imat, self.imat, self.imat @ self.imat)
        self.verify(self.imat, self.fmat, self.imat @ self.fmat)
        self.verify(self.fmat, self.imat, self.fmat @ self.imat)
        self.verify(self.fmat, self.fmat, self.fmat @ self.fmat)

    def verify(self, a, b, ab):
        if not numpy.allclose(a @ b, ab):
            raise ValueError("Mismatch for {} @ {}", a, b)

class TestMatrixMult(ExperimentCase):
    def test_multiple_matrix_mult_types(self):
        self.create(_MatrixMult).run()
