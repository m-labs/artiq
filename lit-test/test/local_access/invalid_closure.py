# RUN: %python -m artiq.compiler.testbench.signature +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

if False:
    t = 1

# CHECK-L: ${LINE:+1}: error: variable 't' can be captured in a closure uninitialized
l = lambda: t

# CHECK-L: ${LINE:+1}: error: variable 't' can be captured in a closure uninitialized
def f():
    return t

l()
f()
