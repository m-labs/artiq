# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: f: ()->NoneType delay(30 mu)
def f():
    for _ in range(10):
        delay_mu(3)

# CHECK-L: g: ()->NoneType delay(60 mu)
def g():
    for _ in range(10):
        for _ in range(2):
            delay_mu(3)
