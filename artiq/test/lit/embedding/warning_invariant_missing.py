# RUN: %python -m artiq.compiler.testbench.embedding +diag %s 2>%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.language.core import *
from artiq.language.types import *

class c:
    kernel_invariants = {"a", "b"}
    a = 0

    def __repr__(self):
        return "<testbench.c object>"

i = c()

@kernel
def entrypoint():
    # CHECK-L: <synthesized>:1: warning: object <testbench.c object> of type <instance testbench.c> declares attribute 'b' as kernel invariant, but the instance referenced here does not have this attribute
    # CHECK-L: ${LINE:+1}: note: expanded from here
    i
