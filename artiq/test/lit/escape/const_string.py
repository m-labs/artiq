# RUN: %python -m artiq.compiler.testbench.embedding %s

from artiq.experiment import *

@kernel
def foo():
    return "x"

@kernel
def entrypoint():
    foo()

    # Test reassigning strings.
    a = "a"
    b = a
