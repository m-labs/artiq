# RUN: env ARTIQ_DUMP_IR=%t %python -m artiq.compiler.testbench.embedding +compile %s
# RUN: OutputCheck %s --file-to-check=%t.txt
# XFAIL: *

from artiq.language.core import *
from artiq.language.types import *

# CHECK-L: call ()->NoneType %local.testbench.entrypoint ; calls testbench.entrypoint

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
