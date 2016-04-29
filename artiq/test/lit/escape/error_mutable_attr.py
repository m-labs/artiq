# RUN: %python -m artiq.compiler.testbench.embedding +diag %s 2>%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.experiment import *

class c:
    x = []

cc = c()

@kernel
def entrypoint():
    # CHECK-L: ${LINE:+1}: error: the assigned value does not outlive the assignment target
    cc.x = [1]
