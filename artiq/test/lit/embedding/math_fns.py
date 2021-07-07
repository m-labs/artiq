# RUN: env ARTIQ_DUMP_LLVM=%t %python -m artiq.compiler.testbench.embedding %s
# RUN: OutputCheck %s --file-to-check=%t.ll

from artiq.language.core import *
from artiq.language.types import *
import numpy

@kernel
def entrypoint():
    # LLVM's constant folding for transcendental functions is good enough that
    # we can do a basic smoke test by just making sure the module compiles and
    # all assertions are statically eliminated.

    # CHECK-NOT: assert
    assert numpy.sin(0.0) == 0.0
    assert numpy.cos(0.0) == 1.0
    assert numpy.exp(0.0) == 1.0
    assert numpy.exp2(1.0) == 2.0
    assert numpy.log(numpy.exp(1.0)) == 1.0
    assert numpy.log10(10.0) == 1.0
    assert numpy.log2(2.0) == 1.0
    assert numpy.fabs(-1.0) == 1.0
    assert numpy.floor(42.5) == 42.0
    assert numpy.ceil(42.5) == 43.0
    assert numpy.trunc(41.5) == 41.0
    assert numpy.rint(41.5) == 42.0
    assert numpy.tan(0.0) == 0.0
    assert numpy.arcsin(0.0) == 0.0
    assert numpy.arccos(1.0) == 0.0
    assert numpy.arctan(0.0) == 0.0
    assert numpy.arctan2(0.0, 1.0) == 0.0
