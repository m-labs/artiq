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
            # The kernel_invariant annotation should generate !invariant.load metadata
            # CHECK: invariant.load
            print("baz")

obj = Class()

@kernel
def entrypoint():
    obj.run()
