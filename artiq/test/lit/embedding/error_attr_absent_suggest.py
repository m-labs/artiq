# RUN: %python -m artiq.compiler.testbench.embedding +diag %s 2>%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.language.core import *
from artiq.language.types import *

class c:
    xx = 1

@kernel
def entrypoint():
    # CHECK-L: <synthesized>:1: error: host object does not have an attribute 'x'; did you mean 'xx'?
    # CHECK-L: ${LINE:+1}: note: expanded from here
    a = c
    # CHECK-L: ${LINE:+1}: note: attribute accessed here
    a.x
