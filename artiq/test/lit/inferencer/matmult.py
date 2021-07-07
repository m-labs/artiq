# RUN: %python -m artiq.compiler.testbench.inferencer %s >%t
# RUN: OutputCheck %s --file-to-check=%t

vec = array([0, 1])
mat = array([[0, 1], [2, 3]])

# CHECK-L: ):numpy.int?
vec @ vec

# CHECK-L: ):numpy.array(elt=numpy.int?, num_dims=1)
vec @ mat

# CHECK-L: ):numpy.array(elt=numpy.int?, num_dims=1)
mat @ vec

# CHECK-L: ):numpy.array(elt=numpy.int?, num_dims=2)
mat @ mat
