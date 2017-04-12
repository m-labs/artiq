# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def f(x):
    x = int64(0)
    return x

# CHECK-L: g: ()->numpy.int64
def g():
    return f(1 + 0)
