# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

assert b"xy" == b"xy"
assert (b"x" + b"y") == b"xy"
