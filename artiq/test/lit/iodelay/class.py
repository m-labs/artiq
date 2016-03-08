# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: g: (i:<instance c>)->NoneType delay(1000000 mu)
def g(i):
    i.f(1.0)

class c:
    def f(self, x):
        delay(x)

g(c())
