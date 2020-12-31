# RUN: %python -m artiq.compiler.testbench.jit %s

a = array([1, 2])

b = +a
assert b[0] == 1
assert b[1] == 2

b = -a
assert b[0] == -1
assert b[1] == -2
