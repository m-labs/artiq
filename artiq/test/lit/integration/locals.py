# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

x = 1
assert x == 1
x += 1
assert x == 2
