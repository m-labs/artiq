# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: f: ()->numpy.int32 delay(30 mu)
def f():
    for _ in range(10):
        delay_mu(3)
    return 10

# CHECK-L: g: (x:float)->numpy.int32
# CHECK-NOT-L: delay
def g(x):
    if x > 1.0:
        return 1
    return 0

g(1.0)
