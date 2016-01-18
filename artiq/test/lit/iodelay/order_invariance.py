# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: g: ()->NoneType delay(2 mu)
def g():
    f()
    f()

def f():
    delay_mu(1)
