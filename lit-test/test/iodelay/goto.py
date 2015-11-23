# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: f: ()->NoneType delay(10 mu)
def f():
    delay_mu(10)
    for _ in range(10):
        break

# CHECK-L: g: ()->NoneType delay(10 mu)
def g():
    delay_mu(10)
    for _ in range(10):
        continue
