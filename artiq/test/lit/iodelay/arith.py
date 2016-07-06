# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: f: (a:numpy.int32, b:numpy.int32, c:numpy.int32, d:numpy.int32, e:numpy.int32)->NoneType delay(s->mu(a * b // c + d - 10 / e) mu)
def f(a, b, c, d, e):
    delay(a * b // c + d - 10 / e)

f(1,2,3,4,5)
