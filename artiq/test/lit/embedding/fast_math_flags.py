# RUN: env ARTIQ_DUMP_UNOPT_LLVM=%t %python -m artiq.compiler.testbench.embedding +compile %s
# RUN: OutputCheck %s --file-to-check=%t_unopt.ll

from artiq.language.core import *
from artiq.language.types import *

# CHECK-L: fmul fast double 1.000000e+00, 0.000000e+00
@kernel(flags=["fast-math"])
def foo():
    core_log(1.0 * 0.0)

# CHECK-L: fmul fast double 2.000000e+00, 0.000000e+00
@portable(flags=["fast-math"])
def bar():
    core_log(2.0 * 0.0)

@kernel
def entrypoint():
    foo()
    bar()
