# RUN: %python -m artiq.compiler.testbench.embedding %s

from artiq.language.core import *
from artiq.language.types import *

class a:
    def foo(self, x):
        print(x)

class b:
    def __init__(self):
        self.obj = a()
        self.meth = self.obj.foo

    @kernel
    def run(self):
        self.meth(1)

bi = b()
@kernel
def entrypoint():
    bi.run()
