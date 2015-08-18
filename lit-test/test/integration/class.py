# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

class c:
    a = 1
    def f():
        return 2

assert c.a == 1
assert c.f() == 2
