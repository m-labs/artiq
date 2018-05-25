# RUN: %python -m artiq.compiler.testbench.embedding %s

from artiq.language.core import *
from artiq.language.types import *

class C:
    @kernel
    def f(self):
        pass

class D(C):
    @kernel
    def f(self):
        # super().f()  # super() not bound
        C.f(self)  # KeyError in compile

di = D()
@kernel
def entrypoint():
    di.f()
