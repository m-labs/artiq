# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s
# REQUIRES: exceptions

try:
    raise ValueError
except ValueError:
    pass
