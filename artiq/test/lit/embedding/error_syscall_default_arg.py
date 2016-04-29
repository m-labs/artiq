# RUN: %python -m artiq.compiler.testbench.embedding +diag %s 2>%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.language.core import *
from artiq.language.types import *

# CHECK-L: ${LINE:+2}: error: system call argument 'x' must not have a default value
@syscall
def foo(x=1) -> TNone:
    pass

@kernel
def entrypoint():
    foo()
