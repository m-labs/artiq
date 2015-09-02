# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: f: ()->NoneType delay(s->mu(1.0) + 1000 mu)
def f():
    delay(1.0)
    delay_mu(1000)

# CHECK-L: g: ()->NoneType delay(s->mu(5.0) mu)
def g():
    delay(1.0)
    delay(2.0 * 2)
