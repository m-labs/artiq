# RUN: %python -m artiq.compiler.testbench.embedding +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.language.core import *
from artiq.language.types import *

# CHECK-L: ${LINE:+1}: error: type annotation for return type, '1', is not an ARTIQ type
def foo() -> 1:
    pass

@kernel
def entrypoint():
    # CHECK-L: ${LINE:+1}: note: in function called remotely here
    foo()
