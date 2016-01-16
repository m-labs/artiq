# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: f: (a:int(width=64), b:int(width=64))->NoneType delay(max(a, b) mu)
def f(a, b):
    with parallel:
        delay_mu(a)
        delay_mu(b)

# CHECK-L: g: (a:int(width=64))->NoneType delay(max(a, 200) mu)
def g(a):
    with parallel:
        delay_mu(100)
        delay_mu(200)
        delay_mu(a)
