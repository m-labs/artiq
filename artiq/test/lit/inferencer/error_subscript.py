# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

x = []

# CHECK-L: ${LINE:+1}: error: multi-dimensional slices are not supported
x[1,2]

# CHECK-L: ${LINE:+1}: error: multi-dimensional slices are not supported
x[1:2,3:4]
