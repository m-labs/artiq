# RUN: %python -m artiq.compiler.testbench.embedding +diag %s 2>%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.language.core import *
from artiq.language.types import *

@kernel
def modify(x):
    # CHECK-L: ${LINE:+1}: error: cannot assign to a tuple element
    x[0] = 2

@kernel
def entrypoint():
    modify((1, "foo", True))
    modify((2, "bar", False))
