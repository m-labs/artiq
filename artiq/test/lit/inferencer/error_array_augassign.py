# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

a = array([[1, 2], [3, 4]])
b = 0.0

# CHECK-L: ${LINE:+1}: error: the result of this operation has type numpy.array(elt=float, num_dims=2), which cannot be assigned to a left-hand side of type float
b /= a

# CHECK-L: ${LINE:+1}: error: the result of this operation has type numpy.array(elt=float, num_dims=2), which cannot be assigned to a left-hand side of type numpy.array(elt=numpy.int?, num_dims=2)
a /= a
