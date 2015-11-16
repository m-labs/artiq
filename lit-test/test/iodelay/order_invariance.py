# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: g: ()->NoneType delay(s->mu(2.0) mu)
def g():
    f()
    f()

def f():
    delay(1.0)
