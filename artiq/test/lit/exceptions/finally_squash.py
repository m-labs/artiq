# RUN: %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t
# REQUIRES: exceptions

def f():
    try:
        1/0
    finally:
        print("f-fin")
        return

def g():
    try:
        f()
    except:
        print("g-except")

# CHECK-L: f-fin
# CHECK-NOT-L: f-out
# CHECK-NOT-L: g-except
g()
