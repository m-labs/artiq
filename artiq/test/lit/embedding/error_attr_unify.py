# RUN: %python -m artiq.compiler.testbench.embedding +diag %s 2>%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.language.core import *
from artiq.language.types import *

class c:
    x = [1, "x"]

@kernel
def entrypoint():
    # CHECK-L: <synthesized>:1: error: cannot unify numpy.int? with str
    # CHECK-NEXT-L: [1, 'x']
    # CHECK-L: ${LINE:+1}: note: expanded from here
    a = c
    # CHECK-L: ${LINE:+1}: note: while inferring a type for an attribute 'x' of a host object
    a.x
