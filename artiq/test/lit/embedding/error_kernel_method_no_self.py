# RUN: %python -m artiq.compiler.testbench.embedding +diag %s 2>%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.language.core import *
from artiq.language.types import *

class c:
    pass
@kernel
def f():
    pass
c.f = f
x = c().f

@kernel
def entrypoint():
    # CHECK-L: <synthesized>:1: error: function 'f()->NoneType delay('a)' of class 'testbench.c' cannot accept a self argument
    # CHECK-L: ${LINE:+1}: note: expanded from here
    x
