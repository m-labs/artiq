# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

assert abs(1234) == 1234
assert abs(-1234) == 1234
assert abs(1234.5) == 1234.5
assert abs(-1234.5) == 1234.5
