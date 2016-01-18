# RUN: env ARTIQ_DUMP_IR=1 %python -m artiq.compiler.testbench.embedding +compile %s 2>%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.language.core import *
from artiq.language.types import *

class foo:
    @kernel
    def bar(self):
        pass
x = foo()

@kernel
def entrypoint():
    # CHECK-L: ; calls testbench.foo.bar
    x.bar()
