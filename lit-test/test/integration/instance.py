# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

class c:
    a = 1

i = c()

# CHECK-L: a 1
print("a", i.a)

def f():
    c = None
    # CHECK-L: shadow a 1
    print("shadow a", i.a)
f()
