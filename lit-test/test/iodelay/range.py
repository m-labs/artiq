# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: f: (a:int(width=32))->NoneType delay(3 * a mu)
def f(a):
    for _ in range(a):
        delay_mu(3)

# CHECK-L: g: (a:int(width=32), b:int(width=32))->NoneType delay(3 * (b - a) mu)
def g(a, b):
    for _ in range(a, b):
        delay_mu(3)

# CHECK-L: h: (a:int(width=32), b:int(width=32), c:int(width=32))->NoneType delay(3 * (b - a) // c mu)
def h(a, b, c):
    for _ in range(a, b, c):
        delay_mu(3)

f(1)
g(1,2)
h(1,2,3)
