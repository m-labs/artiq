# RUN: %python -m artiq.compiler.testbench.embedding +diag %s 2>%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.language.core import *
from artiq.language.types import *

def foo():
    pass

@kernel
def entrypoint():
    # CHECK-L: ${LINE:+1}: fatal: name 'fo0' is not bound to anything; did you mean 'foo'?
    fo0()
