# RUN: %python -m artiq.compiler.testbench.embedding +diag %s 2>%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.experiment import *
import numpy as np

@kernel
def a():
    # CHECK-L: ${LINE:+2}: error: cannot return an allocated value that does not live forever
    # CHECK-L: ${LINE:+1}: note: ... to this point
    return np.full(10, 42.0)


@kernel
def entrypoint():
    a()
