# RUN: env ARTIQ_DUMP_LLVM=%t %python -m artiq.compiler.testbench.embedding +compile %s
# RUN: OutputCheck %s --file-to-check=%t.ll

from artiq.language.core import *
from artiq.language.types import *

class Class:
    kernel_invariants = {"foo"}

    def __init__(self):
        self.foo = True

    @kernel
    def run(self):
        if self.foo:
            print("bar")
        else:
            # Make sure all the code for this branch will be completely elided:
            # CHECK-NOT: baz
            print("baz")

obj = Class()

@kernel
def entrypoint():
    obj.run()
