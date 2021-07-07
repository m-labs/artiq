# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: ${LINE:+1}: error: expected matrix multiplication operand to be of array type
1 @ 2

# CHECK-L: ${LINE:+1}: error: expected matrix multiplication operand to be of array type
[1] @ [2]

# CHECK-L: ${LINE:+1}: error: expected matrix multiplication operand to be 1- or 2-dimensional
array([[[0]]]) @ array([[[1]]])
