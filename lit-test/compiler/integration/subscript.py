# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

lst = list(range(10))
assert lst[0] == 0
assert lst[1] == 1
assert lst[-1] == 9
assert lst[0:1] == [0]
assert lst[0:2] == [0, 1]
assert lst[0:10] == lst
assert lst[1:-1] == lst[1:9]
assert lst[0:1:2] == [0]
assert lst[0:2:2] == [0]
assert lst[0:3:2] == [0, 2]

lst = [0, 0, 0, 0, 0]
lst[0:5:2] = [1, 2, 3]
assert lst == [1, 0, 2, 0, 3]
