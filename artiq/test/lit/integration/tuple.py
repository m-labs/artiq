# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

x, y = 2, 1
x, y = y, x
assert x == 1 and y == 2
assert (1, 2) + (3.0,) == (1, 2, 3.0)

assert (0,) == (0,)
assert (0,) != (1,)

assert ([0],) == ([0],)
assert ([0],) != ([1],)
