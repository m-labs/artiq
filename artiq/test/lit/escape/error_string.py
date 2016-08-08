# RUN: %python -m artiq.compiler.testbench.embedding +diag %s 2>%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.experiment import *

@kernel
def foo():
    # CHECK-NOT-L: ${LINE:+1}: error:
    return "x"

@kernel
def bar():
    # CHECK-L: ${LINE:+1}: error: cannot return an allocated value that does not live forever
    return "x" + "y"

@kernel
def entrypoint():
    foo()
    bar()
