# RUN: %python -m artiq.compiler.testbench.embedding +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.language.core import *
from artiq.language.types import *

class c:
    kernel_constant_attributes = {'a'}

    def __init__(self):
        self.a = 1

i = c()

@kernel
def entrypoint():
    # CHECK-L: ${LINE:+1}: error: cannot assign to constant attribute 'a' of class 'testbench.c'
    i.a = 1
