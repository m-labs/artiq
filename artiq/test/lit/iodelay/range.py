# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: f: (a:numpy.int32)->NoneType delay(3 * a mu)
def f(a):
    for _ in range(a):
        delay_mu(3)

# CHECK-L: g: (a:numpy.int32, b:numpy.int32)->NoneType delay(3 * (b - a) mu)
def g(a, b):
    for _ in range(a, b):
        delay_mu(3)

# CHECK-L: h: (a:numpy.int32, b:numpy.int32, c:numpy.int32)->NoneType delay(3 * (b - a) // c mu)
def h(a, b, c):
    for _ in range(a, b, c):
        delay_mu(3)

f(1)
g(1,2)
h(1,2,3)
