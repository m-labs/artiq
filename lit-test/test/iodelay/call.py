# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def f():
    delay_mu(1)

# CHECK-L: g: ()->NoneType delay(2 mu)
def g():
    f()
    f()
