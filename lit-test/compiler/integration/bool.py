# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

assert (not 0) == True
assert (not 1) == False

assert (0 and 0) is 0
assert (1 and 0) is 0
assert (0 and 1) is 0
assert (1 and 2) is 2

assert (0 or 0) is 0
assert (1 or 0) is 1
assert (0 or 1) is 1
assert (1 or 2) is 1

assert bool(False) is False and bool(False) is False
assert bool(0) is False and bool(1) is True
assert bool(0.0) is False and bool(1.0) is True
x = []; assert bool(x) is False; x = [1]; assert bool(x) is True
assert bool(range(0)) is False and bool(range(1)) is True
