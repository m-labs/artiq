# RUN: env ARTIQ_DUMP_IR=%t ARTIQ_IR_NO_LOC=1 %python -m artiq.compiler.testbench.embedding +compile %s
# RUN: OutputCheck %s --file-to-check=%t.txt

from artiq.language.core import *
from artiq.language.types import *

# CHECK-L:   %LOC.self.FLD.foo = numpy.int32 getattr('foo') <instance testbench.c> %ARG.self
# CHECK-L: for.head:

class c:
    kernel_invariants = {"foo"}

    def __init__(self):
        self.foo = 1

    @kernel
    def run(self):
        for _ in range(10):
            core_log(1.0 * self.foo)

i = c()

@kernel
def entrypoint():
    i.run()
