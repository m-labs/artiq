# RUN: %python -m artiq.compiler.testbench.jit %s

a = array([1, 2, 3])
b = array([4, 5, 6])

c = a + b
assert c[0] == 5
assert c[1] == 7
assert c[2] == 9

c = b - a
assert c[0] == 3
assert c[1] == 3
assert c[2] == 3

c = a * b
assert c[0] == 4
assert c[1] == 10
assert c[2] == 18

c = b // a
assert c[0] == 4
assert c[1] == 2
assert c[2] == 2

c = a ** b
assert c[0] == 1
assert c[1] == 32
assert c[2] == 729

c = b % a
assert c[0] == 0
assert c[1] == 1
assert c[2] == 0

cf = b / a
assert cf[0] == 4.0
assert cf[1] == 2.5
assert cf[2] == 2.0

cf2 = cf + a
assert cf2[0] == 5.0
assert cf2[1] == 4.5
assert cf2[2] == 5.0

d = array([[1, 2], [3, 4]])
e = array([[5, 6], [7, 8]])
f = d + e
assert f[0][0] == 6
assert f[0][1] == 8
assert f[1][0] == 10
assert f[1][1] == 12
