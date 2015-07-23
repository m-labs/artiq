# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

assert 1 < 2 and not (2 < 1)
assert 2 > 1 and not (1 > 2)
assert 1 == 1 and not (1 == 2)
assert 1 != 2 and not (1 != 1)
assert 1 <= 1 and 1 <= 2 and not (2 <= 1)
assert 1 >= 1 and 2 >= 1 and not (1 >= 2)
assert 1 is 1 and not (1 is 2)
assert 1 is not 2 and not (1 is not 1)

x, y = [1], [1]
assert x is x and x is not y
#ARTIQ#assert range(10) is range(10) and range(10) is not range(11)

lst = [1, 2, 3]
assert 1 in lst and 0 not in lst
assert 1 in range(10) and 11 not in range(10) and -1 not in range(10)
