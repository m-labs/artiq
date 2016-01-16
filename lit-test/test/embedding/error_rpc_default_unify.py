# RUN: %python -m artiq.compiler.testbench.embedding +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.language.core import *
from artiq.language.types import *

# CHECK-L: <synthesized>:1: error: cannot unify int(width='a) with str
# CHECK-L: ${LINE:+1}: note: expanded from here while trying to infer a type for an unannotated optional argument 'x' from its default value
def foo(x=[1,"x"]):
    pass

@kernel
def entrypoint():
    # CHECK-L: ${LINE:+1}: note: in function called remotely here
    foo()
