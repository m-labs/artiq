# RUN: %python -m artiq.compiler.testbench.jit %s

a = array([1, 2, 3])
b = array([4, 5, 6])

c = a + b
assert c[0] == 5
assert c[1] == 7
assert c[2] == 9

c = a * b
assert c[0] == 4
assert c[1] == 10
assert c[2] == 18

c = b // a
assert c[0] == 4
assert c[1] == 2
assert c[2] == 2
