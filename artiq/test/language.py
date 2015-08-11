import unittest

from artiq.language.core import *


class LanguageCoreTest(unittest.TestCase):
    def test_unary(self):
        self.assertEqual(int(10),  +int(10))
        self.assertEqual(int(-10), -int(10))
        self.assertEqual(int(~10), ~int(10))
        self.assertEqual(int(10), round(int(10)))

    def test_arith(self):
        self.assertEqual(int(9), int(4) + int(5))
        self.assertEqual(int(9), int(4) + 5)
        self.assertEqual(int(9), 5 + int(4))

        self.assertEqual(9.0, int(4) + 5.0)
        self.assertEqual(9.0, 5.0 + int(4))

        a = int(5)
        a += int(2)
        a += 2
        self.assertEqual(int(9), a)

    def test_compare(self):
        self.assertTrue(int(9) > int(8))
        self.assertTrue(int(9) > 8)
        self.assertTrue(int(9) > 8.0)
        self.assertTrue(9 > int(8))
        self.assertTrue(9.0 > int(8))

    def test_bitwise(self):
        self.assertEqual(int(0x100), int(0x10) << int(4))
        self.assertEqual(int(0x100), int(0x10) << 4)
        self.assertEqual(int(0x100), 0x10 << int(4))

    def test_wraparound(self):
        self.assertEqual(int(0xffffffff), int(-1))
        self.assertTrue(int(0x7fffffff) > int(1))
        self.assertTrue(int(0x80000000) < int(-1))

        self.assertEqual(int(9), int(10) + int(0xffffffff))
        self.assertEqual(-1.0, float(int(0xfffffffe) + int(1)))
