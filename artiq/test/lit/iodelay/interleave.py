# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: f: (a:numpy.int64, b:numpy.int64)->NoneType delay(max(a, b) mu)
def f(a, b):
    with interleave:
        delay_mu(a)
        delay_mu(b)

# CHECK-L: g: (a:numpy.int64)->NoneType delay(max(a, 200) mu)
def g(a):
    with interleave:
        delay_mu(100)
        delay_mu(200)
        delay_mu(a)
