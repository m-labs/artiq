# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

# Basic indexing
a = (1, "xyz", True)

assert a[0] == 1
assert a[1] == "xyz"
assert a[2] == True

# Nested indexing
b = (a, 2, (3, "abc", a))

assert b[0][0] == 1
assert b[1] == 2
assert b[2][2][0] == 1

# Usage on the LHS of an assignment
c = (1, 2, [1, 2, 3])

c[2][0] = 456
assert c[2][0] == 456
