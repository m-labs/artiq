# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: f: (a:int(width=32))->NoneType delay(s->mu(1.5) * a mu)
def f(a):
    for _ in range(a):
        delay(1.5)

# CHECK-L: g: (a:int(width=32), b:int(width=32))->NoneType delay(s->mu(1.5) * (b - a) mu)
def g(a, b):
    for _ in range(a, b):
        delay(1.5)

# CHECK-L: h: (a:int(width=32), b:int(width=32), c:int(width=32))->NoneType delay(s->mu(1.5) * (b - a) // c mu)
def h(a, b, c):
    for _ in range(a, b, c):
        delay(1.5)

f(1)
g(1,2)
h(1,2,3)
