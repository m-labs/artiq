# RUN: %python -m artiq.compiler.testbench.embedding %s

from artiq.experiment import *

class MyClass:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


sl = [MyClass(x=1), MyClass(x=2)]

@kernel
def bug(l):
    for c in l:
        print(c.x)

@kernel
def entrypoint():
    bug(sl)
