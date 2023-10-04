# RUN: %python -m artiq.compiler.testbench.embedding +diag %s 2>%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.language.core import *
from artiq.language.types import *

# CHECK-L: ${LINE:+2}: error: system call argument 'x' must have a type annotation
@syscall
def foo(x) -> TNone:
    pass

@kernel
def entrypoint():
    # CHECK-L: ${LINE:+1}: note: in system call here
    foo()
