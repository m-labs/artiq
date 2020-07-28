# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

a = array([[1, 2], [3, 4]])
b = array([7, 8])

# NumPy supports implicit broadcasting over axes, which we don't (yet).
# Make sure there is a nice error message.
# CHECK-L: ${LINE:+3}: error: dimensions of '+' array operands must match
# CHECK-L: ${LINE:+2}: note: operand of dimension 2
# CHECK-L: ${LINE:+1}: note: operand of dimension 1
a + b
