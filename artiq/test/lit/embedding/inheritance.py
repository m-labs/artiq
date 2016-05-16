# RUN: %python -m artiq.compiler.testbench.embedding %s

from artiq.language.core import *
from artiq.language.types import *

class a:
    @kernel
    def f(self):
        print(self.x)
        return None

class b(a):
    x = 1
class c(a):
    x = 2

bi = b()
ci = c()
@kernel
def entrypoint():
    bi.f()
    ci.f()
