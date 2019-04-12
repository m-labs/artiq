# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

assert abs(1234) == 1234
assert abs(-1234) == 1234
assert abs(1234.0) == 1234.0
assert abs(-1234.0) == 1234
