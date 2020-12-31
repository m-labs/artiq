# RUN: %python -m artiq.compiler.testbench.jit %s

a = array([1, 2, 3])

c = a + 1
assert c[0] == 2
assert c[1] == 3
assert c[2] == 4

c = 1 - a
assert c[0] == 0
assert c[1] == -1
assert c[2] == -2

c = a * 1
assert c[0] == 1
assert c[1] == 2
assert c[2] == 3

c = a // 2
assert c[0] == 0
assert c[1] == 1
assert c[2] == 1

c = a ** 2
assert c[0] == 1
assert c[1] == 4
assert c[2] == 9

c = 2 ** a
assert c[0] == 2
assert c[1] == 4
assert c[2] == 8

c = a % 2
assert c[0] == 1
assert c[1] == 0
assert c[2] == 1

cf = a / 2
assert cf[0] == 0.5
assert cf[1] == 1.0
assert cf[2] == 1.5

cf2 = 2 / array([1, 2, 4])
assert cf2[0] == 2.0
assert cf2[1] == 1.0
assert cf2[2] == 0.5

d = array([[1, 2], [3, 4]])
e = d + 1
assert e[0][0] == 2
assert e[0][1] == 3
assert e[1][0] == 4
assert e[1][1] == 5
