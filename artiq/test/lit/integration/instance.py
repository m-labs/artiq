# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

class c:
    a = 1

i = c()

def f():
    c = None
    assert i.a == 1

assert i.a == 1
f()
