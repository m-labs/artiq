import unittest
import numbers


from artiq.language.environment import BooleanValue, EnumerationValue, \
     NumberValue, DefaultMissing


class NumberValueCase(unittest.TestCase):
    def setUp(self):
        self.default_value = NumberValue()
        self.int_value = NumberValue(42, step=1, ndecimals=0)
        self.float_value = NumberValue(42)

    def test_invalid_default(self):
        with self.assertRaises(ValueError):
            _ = NumberValue("invalid")

        with self.assertRaises(TypeError):
            _ = NumberValue(1.+1j)

    def test_no_default(self):
        with self.assertRaises(DefaultMissing):
            self.default_value.default()

    def test_integer_default(self):
        self.assertIsInstance(self.int_value.default(), numbers.Integral)

    def test_default_to_float(self):
        self.assertIsInstance(self.float_value.default(), numbers.Real)
        self.assertNotIsInstance(self.float_value.default(), numbers.Integral)

    def test_invalid_unit(self):
        with self.assertRaises(KeyError):
            _ = NumberValue(unit="invalid")

    def test_default_scale(self):
        self.assertEqual(self.default_value.scale, 1.)


class BooleanValueCase(unittest.TestCase):
    def setUp(self):
        self.default_value = BooleanValue()
        self.true_value = BooleanValue(True)
        self.false_value = BooleanValue(False)

    def test_default(self):
        self.assertIs(self.true_value.default(), True)
        self.assertIs(self.false_value.default(), False)

    def test_no_default(self):
        with self.assertRaises(DefaultMissing):
            self.default_value.default()

    def test_invalid_default(self):
        with self.assertRaises(ValueError):
            _ = BooleanValue(1)

        with self.assertRaises(ValueError):
            _ = BooleanValue("abc")


class EnumerationValueCase(unittest.TestCase):
    def setUp(self):
        self.default_value = EnumerationValue(["abc"])

    def test_no_default(self):
        with self.assertRaises(DefaultMissing):
            self.default_value.default()

    def test_invalid_default(self):
        with self.assertRaises(ValueError):
            _ = EnumerationValue("abc", "d")

    def test_valid_default(self):
        try:
            _ = EnumerationValue("abc", "a")
        except ValueError:
            self.fail("Unexpected ValueError")
