# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: f: (a:float, b:numpy.int64)->NoneType delay(s->mu(a) + b mu)
def f(a, b):
    delay(a)
    delay_mu(b)
