import unittest
from time import sleep
from typing import Literal

import numpy
from numpy import int32, int64, ndarray

from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase
from artiq.coredevice.comm_kernel import RPCReturnValueError
from artiq.coredevice.core import Core


class _Roundtrip(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    @kernel
    def roundtrip(self, obj, fn):
        fn(obj)

@unittest.skip("NAC3TODO https://git.m-labs.hk/M-Labs/nac3/issues/461")
class RoundtripTest(ExperimentCase):
    def assertRoundtrip(self, obj):
        exp = self.create(_Roundtrip)
        def callback(objcopy):
            self.assertEqual(obj, objcopy)
        exp.roundtrip(obj, callback)

    def assertArrayRoundtrip(self, obj):
        exp = self.create(_Roundtrip)
        def callback(objcopy):
            numpy.testing.assert_array_equal(obj, objcopy)
        exp.roundtrip(obj, callback)

    def test_None(self):
        self.assertRoundtrip(None)

    def test_bool(self):
        self.assertRoundtrip(True)
        self.assertRoundtrip(False)

    def test_numpy_bool(self):
        # These won't return as numpy.bool_, but the bare-Python results should still
        # compare equal.
        self.assertRoundtrip(numpy.True_)
        self.assertRoundtrip(numpy.False_)

    def test_int(self):
        self.assertRoundtrip(int32(42))
        self.assertRoundtrip(int64(42))

    def test_float(self):
        self.assertRoundtrip(42.0)

    def test_str(self):
        self.assertRoundtrip("foo")

    def test_bytes(self):
        self.assertRoundtrip(b"foo")

    def test_bytearray(self):
        self.assertRoundtrip(bytearray(b"foo"))

    def test_list(self):
        self.assertRoundtrip([10])

    def test_bool_list(self):
        self.assertRoundtrip([True, False])

    def test_int64_list(self):
        self.assertRoundtrip([int64(0), int64(1)])

    def test_object(self):
        obj = object()
        self.assertRoundtrip(obj)

    def test_object_list(self):
        self.assertRoundtrip([object(), object()])

    def test_object_tuple(self):
        self.assertRoundtrip((False, object(), True, 0x12345678))

    def test_list_tuple(self):
        self.assertRoundtrip(([1, 2], [3, 4]))

    def test_list_mixed_tuple(self):
        self.assertRoundtrip([
            (0x12345678, [("foo", [0.0, 1.0], [0, 1])]),
            (0x23456789, [("bar", [2.0, 3.0], [2, 3])])])
        self.assertRoundtrip([(0, 1.0, 0), (1, 1.5, 2), (2, 1.9, 4)])

    def test_array_1d(self):
        self.assertArrayRoundtrip(numpy.array([True, False]))
        self.assertArrayRoundtrip(numpy.array([1, 2, 3], dtype=int32))
        self.assertArrayRoundtrip(numpy.array([1.0, 2.0, 3.0]))
        self.assertArrayRoundtrip(numpy.array(["a", "b", "c"]))

    def test_array_2d(self):
        self.assertArrayRoundtrip(numpy.array([[1, 2], [3, 4]], dtype=int32))
        self.assertArrayRoundtrip(numpy.array([[1.0, 2.0], [3.0, 4.0]]))
        self.assertArrayRoundtrip(numpy.array([["a", "b"], ["c", "d"]]))

    # FIXME: This should work, but currently passes as the argument is just
    # synthesised as a call to array() without forwarding the dtype from the host
    # NumPy object.
    @unittest.expectedFailure
    def test_array_jagged(self):
        self.assertArrayRoundtrip(numpy.array([[1, 2], [3]], dtype=object))


@compile
class _DefaultArg(EnvExperiment):
    core: KernelInvariant[Core]

    def build(self):
        self.setattr_device("core")

    @rpc
    def test(self, foo: int32 = 42) -> int32:
        return foo

    # NAC3TODO https://git.m-labs.hk/M-Labs/nac3/issues/101
    @kernel
    def run(self) -> int32:
        return self.test()


class DefaultArgTest(ExperimentCase):
    @unittest.skip("NAC3TODO https://git.m-labs.hk/M-Labs/nac3/issues/528")
    def test_default_arg(self):
        exp = self.create(_DefaultArg)
        self.assertEqual(exp.run(), 42)


@compile
class _RPCTypes(EnvExperiment):
    core: KernelInvariant[Core]

    def build(self):
        self.setattr_device("core")

    @rpc
    def return_bool(self) -> bool:
        return True

    @rpc
    def return_int32(self) -> int32:
        return 1

    @rpc
    def return_int64(self) -> int64:
        return 0x100000000

    @rpc
    def return_float(self) -> float:
        return 1.0

    @rpc
    def return_str(self) -> str:
        return "foo"

    @rpc
    def return_tuple(self) -> tuple[int32, int32]:
        return (1, 2)

    @rpc
    def return_list(self) -> list[int32]:
        return [2, 3]

    @rpc
    def return_array(self) -> ndarray[int32, Literal[1]]:
        return numpy.array([1, 2])

    @rpc
    def return_matrix(self) -> ndarray[int32, Literal[2]]:
        return numpy.array([[1, 2], [3, 4]])

    @rpc
    def return_mismatch(self):
        return b"foo"

    @kernel
    def run_recv(self):
        core_log(self.return_bool())
        core_log(self.return_int32())
        core_log(self.return_int64())
        core_log(self.return_float())
        core_log(self.return_str())
        core_log(self.return_tuple())
        core_log(self.return_list())
        core_log(self.return_array())
        core_log(self.return_matrix())

    def accept(self, value):
        pass

    # NAC3TODO @kernel
    def run_send(self):
        self.accept(True)
        self.accept(1)
        self.accept(0x100000000)
        self.accept(1.0)
        self.accept("foo")
        self.accept((2, 3))
        self.accept([1, 2])
        self.accept(range(10))
        self.accept(numpy.array([1, 2]))
        self.accept(numpy.array([[1, 2], [3, 4]]))
        self.accept(self)

    @kernel
    def run_mismatch(self):
        self.return_mismatch()


class RPCTypesTest(ExperimentCase):
    def test_send(self):
        exp = self.create(_RPCTypes)
        exp.run_send()

    def test_recv(self):
        exp = self.create(_RPCTypes)
        exp.run_send()

    def test_mismatch(self):
        exp = self.create(_RPCTypes)
        with self.assertRaises(RPCReturnValueError):
            exp.run_mismatch()


# NAC3TODO
class _RPCCalls(EnvExperiment):
    core: KernelInvariant[Core]

    def build(self):
        self.setattr_device("core")
        self._list_int64 = [int64(1)]

    def args(self, *args) -> int32:
        return len(args)

    def kwargs(self, x="", **kwargs) -> int32:
        return len(kwargs)

    @kernel
    def args0(self):
        return self.args()

    @kernel
    def args1(self):
        return self.args("A")

    @kernel
    def args2(self):
        return self.args("A", 1)

    @kernel
    def kwargs0(self):
        return self.kwargs()

    @kernel
    def kwargs1(self):
        return self.kwargs(a="A")

    @kernel
    def kwargs2(self):
        return self.kwargs(a="A", b=1)

    @kernel
    def args1kwargs2(self):
        return self.kwargs("X", a="A", b=1)

    @kernel
    def list_int64(self):
        return self._list_int64

    @kernel
    def numpy_things(self):
        return (int32(10), int64(20))

    @kernel
    def builtin(self):
        sleep(1.0)

    @rpc(flags={"async"})
    def async_rpc(self):
        pass

    @kernel
    def async_in_try(self):
        try:
            self.async_rpc()
        except ValueError:
            pass


class RPCCallsTest(ExperimentCase):
    @unittest.skip("NAC3TODO")
    def test_args(self):
        exp = self.create(_RPCCalls)
        self.assertEqual(exp.args0(), 0)
        self.assertEqual(exp.args1(), 1)
        self.assertEqual(exp.args2(), 2)
        self.assertEqual(exp.kwargs0(), 0)
        self.assertEqual(exp.kwargs1(), 1)
        self.assertEqual(exp.kwargs2(), 2)
        self.assertEqual(exp.args1kwargs2(), 2)
        self.assertEqual(exp.numpy_things(),
                         (int32(10), int64(20)))
        # Ensure lists of int64s don't decay to variable-length builtin integers.
        list_int64 = exp.list_int64()
        self.assertEqual(list_int64, [int64(1)])
        self.assertTrue(isinstance(list_int64[0], int64))
        exp.builtin()
        exp.async_in_try()


@compile
class _Annotation(EnvExperiment):
    core: KernelInvariant[Core]

    def build(self):
        self.setattr_device("core")

    @kernel
    def overflow(self, x: int64) -> bool:
        return (x << 32) != int64(0)

    @kernel
    def monomorphize(self, x: list[int32]):
        pass


class AnnotationTest(ExperimentCase):
    def test_annotation(self):
        exp = self.create(_Annotation)
        self.assertEqual(exp.overflow(int64(1)), True)
        exp.monomorphize([])


@compile
class _Async(EnvExperiment):
    core: KernelInvariant[Core]

    def build(self):
        self.setattr_device("core")

    @rpc(flags={"async"})
    def recv_async(self, data: list[int32]):
        pass

    @kernel
    def run(self):
        # fast async path
        self.recv_async([0]*128)
        # slow async path
        self.recv_async([0]*4096)


class AsyncTest(ExperimentCase):
    def test_args(self):
        exp = self.create(_Async)
        exp.run()


@compile
class _Payload1MB(EnvExperiment):
    core: KernelInvariant[Core]

    def build(self):
        self.setattr_device("core")

    @rpc
    def devnull(self, d: list[int32]):
        pass

    @kernel
    def run(self):
        data = [0 for _ in range(1000000//4)]
        self.devnull(data)


class LargePayloadTest(ExperimentCase):
    def test_1MB(self):
        exp = self.create(_Payload1MB)
        exp.run()


@compile
class _ListTuple(EnvExperiment):
    core: KernelInvariant[Core]

    def build(self):
        self.setattr_device("core")

    @kernel
    def run(self):
        # Make sure lifetime for the array data in tuples of lists is managed
        # correctly. This is written in a somewhat convoluted fashion to provoke
        # memory corruption even in the face of compiler optimizations.
        for _ in range(self.get_num_iters()):
            a, b = self.get_values(0, 1, 32)
            c, d = self.get_values(2, 3, 64)
            self.verify(a)
            self.verify(c)
            self.verify(b)
            self.verify(d)

    @kernel
    def verify(self, data: list[int32]):
        for i in range(len(data)):
            if data[i] != data[0] + i:
                raise ValueError

    @rpc
    def get_num_iters(self) -> int32:
        return 2

    @rpc
    def get_values(self, base_a: int32, base_b: int32, n: int32) -> tuple[list[int32], list[int32]]:
        return [int32(base_a + i) for i in range(n)], \
            [int32(base_b + i) for i in range(n)]


@compile
class _NestedTupleList(EnvExperiment):
    core: KernelInvariant[Core]
    data: KernelInvariant[list[tuple[int32, list[tuple[str, list[float], list[int32]]]]]]

    def build(self):
        self.setattr_device("core")
        self.data = [(0x12345678, [("foo", [0.0, 1.0], [2, 3])]),
                     (0x76543210, [("bar", [4.0, 5.0], [6, 7])])]

    @rpc
    def get_data(self) -> list[tuple
            [int32, list[tuple[str, list[float], list[int32]]]]]:
        return self.data

    @kernel
    def run(self):
        a = self.get_data()
        if a != self.data:
            raise ValueError


@compile
class _EmptyList(EnvExperiment):
    core: KernelInvariant[Core]

    def build(self):
        self.setattr_device("core")

    @rpc
    def get_empty(self) -> list[int32]:
        return []

    @kernel
    def run(self):
        a = self.get_empty()
        if a != []:
            raise ValueError


class ListTupleTest(ExperimentCase):
    @unittest.skip("NAC3TODO https://git.m-labs.hk/M-Labs/nac3/issues/529")
    def test_list_tuple(self):
        self.create(_ListTuple).run()

    def test_nested_tuple_list(self):
        self.create(_NestedTupleList).run()

    def test_empty_list(self):
        self.create(_EmptyList).run()


@compile
class _ArrayQuoting(EnvExperiment):
    core: KernelInvariant[Core]
    vec_i32: KernelInvariant[ndarray[int32, Literal[1]]]
    mat_i64: KernelInvariant[ndarray[int64, Literal[2]]]
    arr_f64: KernelInvariant[ndarray[float, Literal[3]]]
    strs: KernelInvariant[ndarray[str, Literal[1]]]

    def build(self):
        self.setattr_device("core")
        self.vec_i32 = numpy.array([0, 1], dtype=int32)
        self.mat_i64 = numpy.array([[0, 1], [2, 3]], dtype=int64)
        self.arr_f64 = numpy.array([[[0.0, 1.0], [2.0, 3.0]],
                                    [[4.0, 5.0], [6.0, 7.0]]])
        self.strs = numpy.array(["foo", "bar"])

    @kernel
    def run(self):
        assert self.vec_i32[0] == 0
        assert self.vec_i32[1] == 1

        assert self.mat_i64[0, 0] == int64(0)
        assert self.mat_i64[0, 1] == int64(1)
        assert self.mat_i64[1, 0] == int64(2)
        assert self.mat_i64[1, 1] == int64(3)

        assert self.arr_f64[0, 0, 0] == 0.0
        assert self.arr_f64[0, 0, 1] == 1.0
        assert self.arr_f64[0, 1, 0] == 2.0
        assert self.arr_f64[0, 1, 1] == 3.0
        assert self.arr_f64[1, 0, 0] == 4.0
        assert self.arr_f64[1, 0, 1] == 5.0
        assert self.arr_f64[1, 1, 0] == 6.0
        assert self.arr_f64[1, 1, 1] == 7.0

        # NAC3TODO https://git.m-labs.hk/M-Labs/nac3/issues/421
        #assert self.strs[0] == "foo"
        #assert self.strs[1] == "bar"


class ArrayQuotingTest(ExperimentCase):
    def test_quoting(self):
        self.create(_ArrayQuoting).run()


@compile
class _Assert(EnvExperiment):
    core: KernelInvariant[Core]

    def build(self):
        self.setattr_device("core")

    @kernel
    def check(self, value: bool):
        assert value

    @kernel
    def check_msg(self, value: bool):
        assert value, "foo"


class AssertTest(ExperimentCase):
    @unittest.skip("NAC3TODO https://git.m-labs.hk/M-Labs/nac3/issues/530")
    def test_assert(self):
        exp = self.create(_Assert)

        def check_fail(fn, msg):
            with self.assertRaises(AssertionError) as ctx:
                fn()
            self.assertEqual(str(ctx.exception), msg)

        exp.check(True)
        check_fail(lambda: exp.check(False), "AssertionError")
        exp.check_msg(True)
        check_fail(lambda: exp.check_msg(False), "foo")


@compile
class _NumpyBool(EnvExperiment):
    core: KernelInvariant[Core]
    np_true: KernelInvariant[bool]
    np_false: KernelInvariant[bool]

    def build(self):
        self.setattr_device("core")
        self.np_true = numpy.True_
        self.np_false = numpy.False_

    @kernel
    def run(self):
        assert self.np_true
        assert self.np_true == True
        assert not self.np_false
        assert self.np_false == False


class NumpyBoolTest(ExperimentCase):
    def test_numpy_bool(self):
        """Test NumPy bools decay to ARTIQ compiler builtin bools as expected"""
        self.create(_NumpyBool).run()


@compile
class _Alignment(EnvExperiment):
    core: KernelInvariant[Core]
    a: KernelInvariant[bool]
    b: KernelInvariant[float]
    c: KernelInvariant[bool]
    d: KernelInvariant[bool]
    e: KernelInvariant[float]
    f: KernelInvariant[bool]

    def build(self):
        self.setattr_device("core")
        self.a = False
        self.b = 1234.5678
        self.c = True
        self.d = True
        self.e = 2345.6789
        self.f = False

    @rpc
    def get_tuples(self) -> list[tuple[bool, float, bool]]:
        return [(self.a, self.b, self.c), (self.d, self.e, self.f)]

    @kernel
    def run(self):
        # Run two RPCs before checking to catch any obvious allocation size calculation
        # issues (i.e. use of uninitialised stack memory).
        tuples0 = self.get_tuples()
        tuples1 = self.get_tuples()
        for tuples in [tuples0, tuples1]:
            a, b, c = tuples[0]
            d, e, f = tuples[1]
            assert a == self.a
            assert b == self.b
            assert c == self.c
            assert d == self.d
            assert e == self.e
            assert f == self.f


class AlignmentTest(ExperimentCase):
    def test_tuple(self):
        self.create(_Alignment).run()


@compile
class _NumpyQuoting(EnvExperiment):
    core: KernelInvariant[Core]

    def build(self):
        self.setattr_device("core")

    @kernel
    def run(self):
        a = np_array([10, 20])
        b = np_sqrt(4.0)


class NumpyQuotingTest(ExperimentCase):
    def test_issue_1871(self):
        """Ensure numpy.array() does not break NumPy math functions"""
        self.create(_NumpyQuoting).run()


@compile
class _IntBoundary(EnvExperiment):
    core: KernelInvariant[Core]
    int32_min: KernelInvariant[int32]
    int32_max: KernelInvariant[int32]
    int64_min: KernelInvariant[int64]
    int64_max: KernelInvariant[int64]

    def build(self):
        self.setattr_device("core")
        self.int32_min = numpy.iinfo(int32).min
        self.int32_max = numpy.iinfo(int32).max
        self.int64_min = int64(numpy.iinfo(int64).min)
        self.int64_max = int64(numpy.iinfo(int64).max)

    @kernel
    def test_int32_bounds(self, min_val: int32, max_val: int32) -> bool:
        return min_val == self.int32_min and max_val == self.int32_max

    @kernel
    def test_int64_bounds(self, min_val: int64, max_val: int64) -> bool:
        return min_val == self.int64_min and max_val == self.int64_max

    @kernel
    def run(self):
        self.test_int32_bounds(self.int32_min, self.int32_max)
        self.test_int64_bounds(self.int64_min, self.int64_max)

class IntBoundaryTest(ExperimentCase):
    def test_int_boundary(self):
        self.create(_IntBoundary).run()


@compile
class _BoolListType(EnvExperiment):
    x: Kernel[list[bool]]
    y: Kernel[list[bool]]

    @rpc
    def assert_bool(self, obj: bool):
        assert isinstance(obj, bool)

    def build(self):
        self.setattr_device("core")
        self.x = [True]
        self.y = [numpy.True_]

    @kernel
    def run_bool(self):
        self.assert_bool(self.x[0])

    @kernel
    def run_numpy_bool(self):
        self.assert_bool(self.y[0])


class BoolListTypeTest(ExperimentCase):
    def test_bool_list(self):
        self.create(_BoolListType).run_bool()

    def test_np_bool_list(self):
        self.create(_BoolListType).run_numpy_bool()


@compile
class _StaticMethods(EnvExperiment):
    core: KernelInvariant[Core]

    def build(self):
        self.setattr_device("core")

    @staticmethod
    @rpc
    def static_rpc_add(a: int32, b: int32) -> int32:
        return a + b

    @rpc
    @staticmethod
    def static_rpc_sub(a: int32, b: int32) -> int32:
        return a - b

    @staticmethod
    @kernel
    def static_kernel_add(a: int32, b: int32) -> int32:
        return a + b

    @kernel
    @staticmethod
    def static_kernel_sub(a: int32, b: int32) -> int32:
        return a - b

    @kernel
    def static_rpc_fn(self) -> int32:
        two = _StaticMethods.static_rpc_sub(3, 1)
        return _StaticMethods.static_rpc_add(1, two)

    @kernel
    def static_kernel_fn(self) -> int32:
        two = _StaticMethods.static_kernel_sub(3, 1)
        return _StaticMethods.static_kernel_add(1, two)

    @kernel
    def static_call_on_instance(self) -> int32:
        return self.static_kernel_add(1, 2)

    @staticmethod
    def static_host(a, b):
        return a + b


class StaticMethodsTest(ExperimentCase):
    def test_rpc_staticmethod(self):
        exp = self.create(_StaticMethods)
        self.assertEqual(exp.static_rpc_fn(), 3)

    def test_kernel_staticmethod(self):
        exp = self.create(_StaticMethods)
        self.assertEqual(exp.static_kernel_fn(), 3)

    def test_host_staticmethod(self):
        self.assertEqual(_StaticMethods.static_host(1, 2), 3)

    def test_static_call_on_instance(self):
        exp = self.create(_StaticMethods)
        self.assertEqual(exp.static_call_on_instance(), 3)
