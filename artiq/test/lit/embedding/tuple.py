# RUN: %python -m artiq.compiler.testbench.embedding %s

from artiq.language.core import *

values = (1, 2)

@kernel
def entrypoint():
    assert values == (1, 2)
