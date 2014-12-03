import unittest
import ast

from artiq.coredevice import comm_dummy, core
from artiq.transforms.unparse import unparse


# Original code before inline:
#
# n = time_to_cycles(1.2345*ns)
# ftw = self.dds.frequency_to_ftw(345*MHz)
# f = self.dds.ftw_to_frequency(ftw)
# phi = 1000*cycles_to_time(n)*f
# do_someting(int(phi))
#
optimize_in = """

def run():
    dds_sysclk = Quantity(Fraction(1000000000, 1), 'Hz')
    n = time_to_cycles((1.2345 * Quantity(Fraction(1, 1000000000), 's')))
    with sequential:
        frequency = (345 * Quantity(Fraction(1000000, 1), 'Hz'))
        frequency_to_ftw_return = int((((2 ** 32) * frequency) / dds_sysclk))
    ftw = frequency_to_ftw_return
    with sequential:
        ftw2 = ftw
        ftw_to_frequency_return = ((ftw2 * dds_sysclk) / (2 ** 32))
    f = ftw_to_frequency_return
    phi = ((1000 * cycles_to_time(n)) * f)
    do_something(int(phi))
"""

optimize_out = """

def run():
    do_something(344)
"""


class OptimizeCase(unittest.TestCase):
    def test_optimize(self):
        coredev = core.Core(comm=comm_dummy.Comm())
        func_def = ast.parse(optimize_in).body[0]
        coredev.transform_stack(func_def, dict(), dict())
        self.assertEqual(unparse(func_def), optimize_out)
