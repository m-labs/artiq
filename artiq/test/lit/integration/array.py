# RUN: %python -m artiq.compiler.testbench.jit %s
# REQUIRES: exceptions

ary = array([1, 2, 3])
assert [x*x for x in ary] == [1, 4, 9]

assert [1] + [2] == [1, 2]
assert [1] * 3 == [1, 1, 1]
