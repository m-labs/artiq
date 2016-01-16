# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

x = "A"
# CHECK-L: ${LINE:+1}: error: assertion message must be a string literal
assert True, x
