# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

assert min(1, 2) == 1
assert max(1, 2) == 2
assert min(1.0, 2.0) == 1.0
assert max(1.0, 2.0) == 2.0
