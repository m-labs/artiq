# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

assert (lambda: 1)() == 1
assert (lambda x: x)(1) == 1
assert (lambda x, y: x + y)(1, 2) == 3
assert (lambda x, y=1: x + y)(1) == 2
assert (lambda x, y=1: x + y)(1, 2) == 3
assert (lambda x, y=1: x + y)(x=3) == 4
assert (lambda x, y=1: x + y)(y=2, x=3) == 5
