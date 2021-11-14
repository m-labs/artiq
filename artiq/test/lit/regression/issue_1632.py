# RUN: %python -m artiq.compiler.testbench.embedding %s

from artiq.language.core import *
from artiq.language.types import *
import numpy as np

class A:
    def __init__(self):
        self.n = 2

    @kernel
    def run(self):
        print([1, 2, 3][:self.n])

a = A()

@kernel
def entrypoint():
    a.run()
