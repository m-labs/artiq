# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: ${LINE:+1}: error: array cannot be invoked with the arguments ()
a = array()

b = array([1, 2, 3])

# CHECK-L: ${LINE:+1}: error: too many indices for array of dimension 1
b[1, 2]

# CHECK-L: ${LINE:+1}: error: strided slicing not yet supported for NumPy arrays
b[::-1]

# CHECK-L: ${LINE:+1}: error: array attributes cannot be assigned to
b.shape = (5, )
