# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: f: ()->NoneType delay(1001000 mu)
def f():
    delay(1.0)
    delay_mu(1000)

# CHECK-L: g: ()->NoneType delay(3 mu)
def g():
    delay_mu(1)
    delay_mu(2)
