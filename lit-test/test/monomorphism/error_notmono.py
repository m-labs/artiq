# RUN: %python -m artiq.compiler.testbench.signature +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: ${LINE:+1}: error: the type of this expression cannot be fully inferred
x = int(1)

# CHECK-L: ${LINE:+1}: error: the return type of this function cannot be fully inferred
def fn():
    return int(1)
