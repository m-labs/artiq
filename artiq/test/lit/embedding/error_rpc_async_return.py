# RUN: %python -m artiq.compiler.testbench.embedding +diag %s 2>%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.language.core import *
from artiq.language.types import *

# CHECK-L: ${LINE:+2}: fatal: functions that return a value cannot be defined as async RPCs
@rpc(flags={"async"})
def foo() -> TInt32:
    pass

@kernel
def entrypoint():
    # CHECK-L: ${LINE:+1}: note: function called here
    foo()
