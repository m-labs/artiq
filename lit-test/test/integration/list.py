# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

[x, y] = [1, 2]
assert (x, y) == (1, 2)

lst = [1, 2, 3]
assert [x*x for x in lst] == [1, 4, 9]
