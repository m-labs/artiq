# RUN: %python -m artiq.compiler.testbench.inferencer %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: numpy.array(elt='a)
array([])

# CHECK-L: numpy.array(elt=numpy.int?)
array([1, 2, 3])
# CHECK-L: numpy.array(elt=numpy.int?)
array([[1, 2, 3], [4, 5, 6]])

# CHECK-L: numpy.array(elt=list(elt=numpy.int?))
array([[1, 2, 3], [4, 5]])
