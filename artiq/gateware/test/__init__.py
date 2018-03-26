import unittest

try:
    import migen
except ImportError:
    def load_tests(*args, **kwargs):
        raise unittest.SkipTest("migen unavailable")
