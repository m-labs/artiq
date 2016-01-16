# RUN: %python -m artiq.compiler.testbench.embedding %s

from artiq.language.core import *
from artiq.language.types import *

class c:
    def p(self, foo):
        print(foo)
i = c()

@kernel
def entrypoint():
    i.p("foo")
    i.p(42)
