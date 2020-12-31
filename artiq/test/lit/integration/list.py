# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s
# REQUIRES: exceptions

[x, y] = [1, 2]
assert (x, y) == (1, 2)

lst = [1, 2, 3]
assert [x*x for x in lst] == [1, 4, 9]

assert [0] == [0]
assert [0] != [1]
assert [[0]] == [[0]]
assert [[0]] != [[1]]
assert [[[0]]] == [[[0]]]
assert [[[0]]] != [[[1]]]

assert [1] + [2] == [1, 2]
assert [1] * 3 == [1, 1, 1]
