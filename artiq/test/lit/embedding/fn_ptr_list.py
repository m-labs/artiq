# RUN: %python -m artiq.compiler.testbench.embedding %s

from artiq.language.core import *
from artiq.language.types import *

@kernel
def a():
    pass

fns = [a, a]

@kernel
def entrypoint():
    fns[0]()
    fns[1]()
