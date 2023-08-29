# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

i = 0
x = (1, "foo", True)

# CHECK-L: ${LINE:+1}: error: tuples can only be indexed by a constant
x[i]

# CHECK-L: ${LINE:+1}: error: tuples can only be indexed by a constant
x[0:2]
