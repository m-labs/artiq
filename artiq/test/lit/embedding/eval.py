# RUN: %python -m artiq.compiler.testbench.embedding %s

from artiq.language.core import *


def make_incrementer(increment):
    return kernel_from_string(["a"], "return a + {}".format(increment),
                              portable)


foo = make_incrementer(1)
bar = make_incrementer(2)


@kernel
def entrypoint():
    assert foo(4) == 5
    assert bar(4) == 6
