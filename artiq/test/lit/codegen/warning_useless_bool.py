# RUN: %python -m artiq.compiler.testbench.signature +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: ${LINE:+1}: warning: this expression, which is always truthful, is coerced to bool
bool(IndexError())
