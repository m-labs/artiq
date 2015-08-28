# RUN: %python -m artiq.compiler.testbench.embedding %s >%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.language.core import *
from artiq.language.types import *

# CHECK-L: ${LINE:+1}: error: function must have a return type annotation to be called remotely
def foo():
    pass

@kernel
def entrypoint():
    # CHECK-L: ${LINE:+1}: note: in function called remotely here
    foo()
