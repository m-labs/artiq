# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

a = 1
# CHECK-L: ${LINE:+1}: error: the width argument of int() must be an integer literal
int(1.0, width=a)

# CHECK-L: ${LINE:+1}: error: the argument of len() must be of an iterable type
len(1)

# CHECK-L: ${LINE:+1}: error: the argument of list() must be of an iterable type
list(1)

# CHECK-L: ${LINE:+1}: error: an argument of range() must be of an integer type
range([])
