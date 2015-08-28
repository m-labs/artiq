# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

class c:
    a = 1
    def f():
        return 2
    def g(self):
        return self.a + 5
    def h(self, x):
        return self.a + x

assert c.a == 1
assert c.f() == 2
assert c().g() == 6
assert c().h(9) == 10
