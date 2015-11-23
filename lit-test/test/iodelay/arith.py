# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: f: (a:int(width=32), b:int(width=32), c:int(width=32), d:int(width=32), e:int(width=32))->NoneType delay(s->mu(a * b // c + d - 10 / e) mu)
def f(a, b, c, d, e):
    delay(a * b // c + d - 10 / e)

f(1,2,3,4,5)
