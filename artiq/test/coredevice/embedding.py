from artiq.language import *
from artiq.test.hardware_testbench import ExperimentCase


class Roundtrip(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    @kernel
    def roundtrip(self, obj, fn):
        fn(obj)


class RoundtripTest(ExperimentCase):
    def assertRoundtrip(self, obj):
        exp = self.create(Roundtrip)
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
