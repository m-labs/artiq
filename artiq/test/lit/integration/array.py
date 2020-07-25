# RUN: %python -m artiq.compiler.testbench.jit %s
# REQUIRES: exceptions

ary = array([1, 2, 3])
assert len(ary) == 3
# FIXME: Implement ndarray indexing
# assert [x*x for x in ary] == [1, 4, 9]

matrix = array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
assert len(matrix) == 2
