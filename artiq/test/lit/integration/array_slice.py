# RUN: %python -m artiq.compiler.testbench.jit %s

a = array([0, 1, 2, 3])

b = a[2:3]
assert b.shape == (1,)
assert b[0] == 2
b[0] = 5
assert a[2] == 5

b = a[3:2]
assert b.shape == (0,)

c = array([[0, 1], [2, 3]])

d = c[:1]
assert d.shape == (1, 2)
assert d[0, 0] == 0
assert d[0, 1] == 1
d[0, 0] = 5
assert c[0, 0] == 5

d = c[1:0]
assert d.shape == (0, 2)
