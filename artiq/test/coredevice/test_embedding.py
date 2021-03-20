import numpy
import unittest
from time import sleep

from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase
from artiq.coredevice.comm_kernel import RPCReturnValueError


class _Roundtrip(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    @kernel
    def roundtrip(self, obj, fn):
        fn(obj)


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
        self.assertRoundtrip(numpy.int32(42))
        self.assertRoundtrip(numpy.int64(42))

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

    def test_object(self):
        obj = object()
        self.assertRoundtrip(obj)

    def test_object_list(self):
        self.assertRoundtrip([object(), object()])

    def test_list_tuple(self):
        self.assertRoundtrip(([1, 2], [3, 4]))

    def test_list_mixed_tuple(self):
        self.assertRoundtrip([(0x12345678, [("foo", [0.0, 1.0], [0, 1])])])

    def test_array_1d(self):
        self.assertArrayRoundtrip(numpy.array([True, False]))
        self.assertArrayRoundtrip(numpy.array([1, 2, 3], dtype=numpy.int32))
        self.assertArrayRoundtrip(numpy.array([1.0, 2.0, 3.0]))
        self.assertArrayRoundtrip(numpy.array(["a", "b", "c"]))

    def test_array_2d(self):
        self.assertArrayRoundtrip(numpy.array([[1, 2], [3, 4]], dtype=numpy.int32))
        self.assertArrayRoundtrip(numpy.array([[1.0, 2.0], [3.0, 4.0]]))
        self.assertArrayRoundtrip(numpy.array([["a", "b"], ["c", "d"]]))

    # FIXME: This should work, but currently passes as the argument is just
    # synthesised as a call to array() without forwarding the dype form the host
    # NumPy object.
    @unittest.expectedFailure
    def test_array_jagged(self):
        self.assertArrayRoundtrip(numpy.array([[1, 2], [3]], dtype=object))


class _DefaultArg(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    def test(self, foo=42) -> TInt32:
        return foo

    @kernel
    def run(self):
        return self.test()


class DefaultArgTest(ExperimentCase):
    def test_default_arg(self):
        exp = self.create(_DefaultArg)
        self.assertEqual(exp.run(), 42)


class _RPCTypes(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    def return_bool(self) -> TBool:
        return True

    def return_int32(self) -> TInt32:
        return 1

    def return_int64(self) -> TInt64:
        return 0x100000000

    def return_float(self) -> TFloat:
        return 1.0

    def return_str(self) -> TStr:
        return "foo"

    def return_bytes(self) -> TBytes:
        return b"foo"

    def return_bytearray(self) -> TByteArray:
        return bytearray(b"foo")

    def return_tuple(self) -> TTuple([TInt32, TInt32]):
        return (1, 2)

    def return_list(self) -> TList(TInt32):
        return [2, 3]

    def return_range(self) -> TRange32:
        return range(10)

    def return_array(self) -> TArray(TInt32):
        return numpy.array([1, 2])

    def return_matrix(self) -> TArray(TInt32, 2):
        return numpy.array([[1, 2], [3, 4]])

    def return_mismatch(self):
        return b"foo"

    @kernel
    def run_recv(self):
        core_log(self.return_bool())
        core_log(self.return_int32())
        core_log(self.return_int64())
        core_log(self.return_float())
        core_log(self.return_str())
        core_log(self.return_bytes())
        core_log(self.return_bytearray())
        core_log(self.return_tuple())
        core_log(self.return_list())
        core_log(self.return_range())
        core_log(self.return_array())
        core_log(self.return_matrix())

    def accept(self, value):
        pass

    @kernel
    def run_send(self):
        self.accept(True)
        self.accept(1)
        self.accept(0x100000000)
        self.accept(1.0)
        self.accept("foo")
        self.accept(b"foo")
        self.accept(bytearray(b"foo"))
        self.accept(bytes([1, 2]))
        self.accept(bytearray([1, 2]))
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


class _RPCCalls(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    def args(self, *args) -> TInt32:
        return len(args)

    def kwargs(self, x="", **kwargs) -> TInt32:
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
    def numpy_things(self):
        return (numpy.int32(10), numpy.int64(20), numpy.array([42,]))

    @kernel
    def numpy_full(self):
        return numpy.full(10, 20)

    @kernel
    def numpy_full_matrix(self):
        return numpy.full((3, 2), 13)

    @kernel
    def numpy_nan(self):
        return numpy.full(10, numpy.nan)

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
                         (numpy.int32(10), numpy.int64(20), numpy.array([42,])))
        self.assertTrue((exp.numpy_full() == numpy.full(10, 20)).all())
        self.assertTrue((exp.numpy_full_matrix() == numpy.full((3, 2), 13)).all())
        self.assertTrue(numpy.isnan(exp.numpy_nan()).all())
        exp.builtin()
        exp.async_in_try()


class _Annotation(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    @kernel
    def overflow(self, x: TInt64) -> TBool:
        return (x << 32) != 0

    @kernel
    def monomorphize(self, x: TList(TInt32)):
        pass


class AnnotationTest(ExperimentCase):
    def test_annotation(self):
        exp = self.create(_Annotation)
        self.assertEqual(exp.overflow(1), True)
        exp.monomorphize([])

class _Async(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    @rpc(flags={"async"})
    def recv_async(self, data):
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


class _Payload1MB(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    def devnull(self, d):
        pass

    @kernel
    def run(self):
        data = [0 for _ in range(1000000//4)]
        self.devnull(data)


class LargePayloadTest(ExperimentCase):
    def test_1MB(self):
        exp = self.create(_Payload1MB)
        exp.run()


class _ListTuple(EnvExperiment):
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
    def verify(self, data):
        for i in range(len(data)):
            if data[i] != data[0] + i:
                raise ValueError

    def get_num_iters(self) -> TInt32:
        return 2

    def get_values(self, base_a, base_b, n) -> TTuple([TList(TInt32), TList(TInt32)]):
        return [numpy.int32(base_a + i) for i in range(n)], \
            [numpy.int32(base_b + i) for i in range(n)]


class _NestedTupleList(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.data = [(0x12345678, [("foo", [0.0, 1.0], [2, 3])]),
                     (0x76543210, [("bar", [4.0, 5.0], [6, 7])])]

    def get_data(self) -> TList(TTuple(
            [TInt32, TList(TTuple([TStr, TList(TFloat), TList(TInt32)]))])):
        return self.data

    @kernel
    def run(self):
        a = self.get_data()
        if a != self.data:
            raise ValueError


class _EmptyList(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    def get_empty(self) -> TList(TInt32):
        return []

    @kernel
    def run(self):
        a = self.get_empty()
        if a != []:
            raise ValueError


class ListTupleTest(ExperimentCase):
    def test_list_tuple(self):
        self.create(_ListTuple).run()

    def test_nested_tuple_list(self):
        self.create(_NestedTupleList).run()

    def test_empty_list(self):
        self.create(_EmptyList).run()


class _ArrayQuoting(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.vec_i32 = numpy.array([0, 1], dtype=numpy.int32)
        self.mat_i64 = numpy.array([[0, 1], [2, 3]], dtype=numpy.int64)
        self.arr_f64 = numpy.array([[[0.0, 1.0], [2.0, 3.0]],
                                    [[4.0, 5.0], [6.0, 7.0]]])
        self.strs = numpy.array(["foo", "bar"])

    @kernel
    def run(self):
        assert self.vec_i32[0] == 0
        assert self.vec_i32[1] == 1

        assert self.mat_i64[0, 0] == 0
        assert self.mat_i64[0, 1] == 1
        assert self.mat_i64[1, 0] == 2
        assert self.mat_i64[1, 1] == 3

        assert self.arr_f64[0, 0, 0] == 0.0
        assert self.arr_f64[0, 0, 1] == 1.0
        assert self.arr_f64[0, 1, 0] == 2.0
        assert self.arr_f64[0, 1, 1] == 3.0
        assert self.arr_f64[1, 0, 0] == 4.0
        assert self.arr_f64[1, 0, 1] == 5.0
        assert self.arr_f64[1, 1, 0] == 6.0
        assert self.arr_f64[1, 1, 1] == 7.0

        assert self.strs[0] == "foo"
        assert self.strs[1] == "bar"


class ArrayQuotingTest(ExperimentCase):
    def test_quoting(self):
        self.create(_ArrayQuoting).run()


class _Assert(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    @kernel
    def check(self, value):
        assert value

    @kernel
    def check_msg(self, value):
        assert value, "foo"


class AssertTest(ExperimentCase):
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


class _NumpyBool(EnvExperiment):
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
