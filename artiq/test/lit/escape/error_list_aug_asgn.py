# RUN: %python -m artiq.compiler.testbench.embedding +diag %s 2>%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.experiment import *

@kernel
def entrypoint():
    a = [1,2]
    # CHECK-L: ${LINE:+2}: error: lists cannot be mutated in-place
    # CHECK-L: ${LINE:+1}: note: try using `a = a + [3,4]`
    a += [3,4]

