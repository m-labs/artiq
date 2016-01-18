# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

class c:
    a = 1

i = c()

assert i.a == 1

def f():
    c = None
    assert i.a == 1
f()
