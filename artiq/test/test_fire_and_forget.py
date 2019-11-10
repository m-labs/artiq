import unittest

from artiq.protocols import fire_and_forget


class FireAndForgetCase(unittest.TestCase):
    def _set_ok(self):
        self.ok = True

    def test_fire_and_forget(self):
        self.ok = False
        p = fire_and_forget.FFProxy(self)
        p._set_ok()
        with self.assertRaises(AttributeError):
            p.non_existing_method
        p.ff_join()
        self.assertTrue(self.ok)
