# RUN: %python -m artiq.compiler.testbench.embedding +diag %s 2>%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.experiment import *

@kernel
def leak(a):
    return a

@kernel
def entrypoint():
    # CHECK-L: ${LINE:+2}: error: cannot return an allocated value that does not live forever
    # CHECK-L: ${LINE:+1}: note: ... to this point
    return leak([1, 2, 3])
