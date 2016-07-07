# RUN: %python -m artiq.compiler.testbench.embedding +diag %s 2>%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.language.core import *
from artiq.language.types import *

class foo:
    # CHECK-L: ${LINE:+2}: fatal: this function cannot be called as an RPC
    @host_only
    def pause(self):
        pass

x = foo()

@kernel
def entrypoint():
    # CHECK-L: ${LINE:+2}: note: in function called remotely here
    # CHECK-L: ${LINE:+1}: note: while inferring a type for an attribute 'pause' of a host object
    x.pause()
