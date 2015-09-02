# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: f: ()->int(width=32) delay(s->mu(1.5) * 10 mu)
def f():
    for _ in range(10):
        delay(1.5)
    return 10

# CHECK-L: g: (x:float)->int(width=32) delay(0 mu)
def g(x):
    if x > 1.0:
        return 1
    return 0

g(1.0)
