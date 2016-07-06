# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

try:
    pass
# CHECK-L: ${LINE:+1}: error: this expression must refer to an exception constructor
except 1:
    pass

try:
    pass
# CHECK-L: ${LINE:+1}: error: cannot unify numpy.int? with Exception
except Exception as e:
    e = 1
