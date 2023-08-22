# RUN: %python -m artiq.compiler.testbench.embedding +diag %s 2>%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.language.core import *
from artiq.language.types import *

# CHECK-L: ${LINE:+2}: error: subkernel argument 'x' must not have a default value
@subkernel(destination=1)
def foo(x: TInt32=1) -> TNone:
    pass

@kernel
def entrypoint():
    foo()
