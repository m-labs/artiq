from time import sleep

from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase


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
        self.assertRoundtrip(42)
        self.assertRoundtrip(int(42, width=64))

    def test_float(self):
        self.assertRoundtrip(42.0)

    def test_str(self):
        self.assertRoundtrip("foo")

    def test_list(self):
        self.assertRoundtrip([10])

    def test_object(self):
        obj = object()
        self.assertRoundtrip(obj)


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


class _RPC(EnvExperiment):
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
    def builtin(self):
        sleep(1.0)

class RPCTest(ExperimentCase):
    def test_args(self):
        exp = self.create(_RPC)
        self.assertEqual(exp.args0(), 0)
        self.assertEqual(exp.args1(), 1)
        self.assertEqual(exp.args2(), 2)
        self.assertEqual(exp.kwargs0(), 0)
        self.assertEqual(exp.kwargs1(), 1)
        self.assertEqual(exp.kwargs2(), 2)
        self.assertEqual(exp.args1kwargs2(), 2)
        exp.builtin()


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
