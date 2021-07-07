# RUN: %python -m artiq.compiler.testbench.jit %s

mat23 = array([[1, 2, 3], [4, 5, 6]])
mat32 = array([[1, 2], [3, 4], [5, 6]])
vec2 = array([1, 2])
vec3 = array([1, 2, 3])

assert vec3 @ vec3 == 14

a = mat23 @ mat32
assert a.shape == (2, 2)
assert a[0][0] == 22
assert a[0][1] == 28
assert a[1][0] == 49
assert a[1][1] == 64

b = mat23 @ vec3
assert b.shape == (2,)
assert b[0] == 14
assert b[1] == 32

b = vec3 @ mat32
assert b.shape == (2,)
assert b[0] == 22
assert b[1] == 28
