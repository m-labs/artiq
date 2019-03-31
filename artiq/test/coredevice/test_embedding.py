import numpy
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

    def test_None(self):
        self.assertRoundtrip(None)

    def test_bool(self):
        self.assertRoundtrip(True)
        self.assertRoundtrip(False)

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

    def test_array(self):
        self.assertRoundtrip(numpy.array([10]))

    def test_object(self):
        obj = object()
        self.assertRoundtrip(obj)

    def test_object_list(self):
        self.assertRoundtrip([object(), object()])

    def test_list_tuple(self):
        self.assertRoundtrip(([1, 2], [3, 4]))

    def test_list_mixed_tuple(self):
        self.assertRoundtrip([(0x12345678, [("foo", [0.0, 1.0], [0, 1])])])


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
