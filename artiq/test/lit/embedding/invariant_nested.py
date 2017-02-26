# RUN: %python -m artiq.compiler.testbench.embedding %s

from artiq.language.core import *
from artiq.language.types import *


class ClassA:
    def __init__(self):
        self.foo = False


class ClassB:
    kernel_invariants = {"bar"}

    def __init__(self):
        self.bar = ClassA()

obj = ClassB()

@kernel
def entrypoint():
    obj.bar.foo = True
