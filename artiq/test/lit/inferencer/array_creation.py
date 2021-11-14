# RUN: %python -m artiq.compiler.testbench.inferencer %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: numpy.array(elt='a, num_dims=1)
array([])
# CHECK-L: numpy.array(elt='b, num_dims=2)
array([[], []])

# CHECK-L: numpy.array(elt=numpy.int?, num_dims=1)
array([1, 2, 3])
# CHECK-L: numpy.array(elt=numpy.int?, num_dims=2)
array([[1, 2, 3], [4, 5, 6]])

# Jagged arrays produce runtime failure:
# CHECK-L: numpy.array(elt=numpy.int?, num_dims=2)
array([[1, 2, 3], [4, 5]])
