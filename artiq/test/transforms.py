import unittest
import ast

from artiq import ns
from artiq.coredevice import comm_dummy, core
from artiq.transforms.unparse import unparse


optimize_in = """

def run():
    dds_sysclk = Fraction(1000000000, 1)
    n = seconds_to_mu((1.2345 * Fraction(1, 1000000000)))
    with sequential:
        frequency = 345 * Fraction(1000000, 1)
        frequency_to_ftw_return = int((((2 ** 32) * frequency) / dds_sysclk))
    ftw = frequency_to_ftw_return
    with sequential:
        ftw2 = ftw
        ftw_to_frequency_return = ((ftw2 * dds_sysclk) / (2 ** 32))
    f = ftw_to_frequency_return
    phi = ((1000 * mu_to_seconds(n)) * f)
    do_something(int(phi))
"""

optimize_out = """

def run():
    now = syscall('now_init')
    try:
        do_something(344)
    finally:
        syscall('now_save', now)
"""


class OptimizeCase(unittest.TestCase):
    def test_optimize(self):
        dmgr = dict()
        dmgr["comm"] = comm_dummy.Comm(dmgr)
        coredev = core.Core(dmgr, ref_period=1*ns)
        func_def = ast.parse(optimize_in).body[0]
        coredev.transform_stack(func_def, dict(), dict())
        self.assertEqual(unparse(func_def), optimize_out)
