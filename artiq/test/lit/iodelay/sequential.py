# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: f: (a:numpy.int64, b:numpy.int64)->NoneType delay(a + b mu)
def f(a, b):
    with sequential:
        delay_mu(a)
        delay_mu(b)
