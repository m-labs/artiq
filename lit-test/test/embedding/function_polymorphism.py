# RUN: %python -m artiq.compiler.testbench.embedding %s

from artiq.language.core import *
from artiq.language.types import *

def f(x):
    print(x)

@kernel
def entrypoint():
    f("foo")
    f(42)
