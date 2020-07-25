# RUN: %python -m artiq.compiler.testbench.jit %s
# REQUIRES: exceptions

ary = array([1, 2, 3])
assert len(ary) == 3
assert ary.shape == [3]
# FIXME: Implement ndarray indexing
# assert [x*x for x in ary] == [1, 4, 9]

# Reassign to an existing value to disambiguate type of empty array.
empty_array = array([1])
empty_array = array([])
assert len(empty_array) == 0
assert empty_array.shape == [0]

matrix = array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
assert len(matrix) == 2
assert matrix.shape == [2, 3]
