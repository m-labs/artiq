# RUN: %python -m artiq.compiler.testbench.inferencer %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# Nothing known, as there could be several more dimensions
# hidden from view by the array being empty.
# CHECK-L: ([]:list(elt='a)):'b
array([])

# CHECK-L: numpy.array(elt=numpy.int?, num_dims=1)
array([1, 2, 3])
# CHECK-L: numpy.array(elt=numpy.int?, num_dims=2)
array([[1, 2, 3], [4, 5, 6]])

# Jagged arrays produce runtime failure:
# CHECK-L: numpy.array(elt=numpy.int?, num_dims=2)
array([[1, 2, 3], [4, 5]])
