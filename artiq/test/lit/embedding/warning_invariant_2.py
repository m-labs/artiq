# RUN: %python -m artiq.compiler.testbench.embedding +diag %s 2>%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.language.core import *
from artiq.language.types import *

class c:
    a = b = 0
    def __init__(self, invariants):
        self.kernel_invariants = invariants

    def __repr__(self):
        return "<testbench.c object>"

i1 = c({"a", "b"})
i2 = c({"a"})

@kernel
def entrypoint():
    # CHECK-L: <synthesized>:1: warning: object <testbench.c object> of type <instance testbench.c> does not declare attribute(s) 'b' as kernel invariant, but other objects of the same type do; the invariant annotation on other objects will be ignored
    # CHECK-L: ${LINE:+1}: note: expanded from here
    [i1, i2]
