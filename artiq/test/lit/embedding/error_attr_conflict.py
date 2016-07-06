# RUN: %python -m artiq.compiler.testbench.embedding +diag %s 2>%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.language.core import *
from artiq.language.types import *

class c:
    pass

i1 = c()
i1.x = 1

i2 = c()
i2.x = 1.0

@kernel
def entrypoint():
    # CHECK-L: <synthesized>:1: error: host object has an attribute 'x' of type float, which is different from previously inferred type numpy.int32 for the same attribute
    i1.x
    # CHECK-L: ${LINE:+1}: note: expanded from here
    i2.x
