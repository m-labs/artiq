# RUN: %python -m artiq.compiler.testbench.embedding %s >%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.language.core import *
from artiq.language.types import *

@kernel
def entrypoint():
    # CHECK-L: ${LINE:+1}: fatal: name 'prnt' is not bound to anything; did you mean 'print'?
    prnt()
