# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: ${LINE:+1}: error: the 'parallel' context manager must be the only one in a 'with' statement
with parallel, sequential:
    pass
