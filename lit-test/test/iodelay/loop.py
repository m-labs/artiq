# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: f: ()->NoneType delay(s->mu(1.5) * 10 mu)
def f():
    for _ in range(10):
        delay(1.5)

# CHECK-L: g: ()->NoneType delay(s->mu(1.5) * 2 * 10 mu)
def g():
    for _ in range(10):
        for _ in range(2):
            delay(1.5)
