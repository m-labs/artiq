# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: ${LINE:+1}: error: type bytes is not mutable
(b"a")[0] = 1
