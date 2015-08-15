# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

class c:
    a = 1
    def f():
        return 2

# CHECK-L: a 1
print("a", c.a)
# CHECK-L: f() 2
print("f()", c.f())
