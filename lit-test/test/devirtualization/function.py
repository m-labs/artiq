# RUN: env ARTIQ_DUMP_IR=1 %python -m artiq.compiler.testbench.embedding +compile %s 2>%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.language.core import *
from artiq.language.types import *

# CHECK-L: call ()->NoneType delay('b) %local.testbench.entrypoint ; calls testbench.entrypoint

@kernel
def baz():
    pass

class foo:
    @kernel
    def bar(self):
        # CHECK-L: call ()->NoneType %local.testbench.baz ; calls testbench.baz
        baz()
x = foo()

@kernel
def entrypoint():
    x.bar()
