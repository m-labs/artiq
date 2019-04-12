# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: ${LINE:+1}: error: the argument of len() must be of an iterable type
len(1)

# CHECK-L: ${LINE:+1}: error: the argument of list() must be of an iterable type
list(1)

# CHECK-L: ${LINE:+1}: error: the arguments of min() must be of a numeric type
min([1], [1])

# CHECK-L: ${LINE:+1}: error: the arguments of abs() must be of a numeric type
abs([1.0])

# CHECK-L: ${LINE:+1}: error: strings currently cannot be constructed
str(1)
