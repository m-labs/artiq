# RUN: %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t
# REQUIRES: exceptions

def f():
    try:
        1/0
    finally:
        print("f-fin")
        raise ValueError()

def g():
    try:
        f()
    except ZeroDivisionError:
        print("g-except-zde")
    except ValueError:
        print("g-except-ve")

# CHECK-L: f-fin
# CHECK-L: g-except-ve
# CHECK-NOT-L: g-except-zde
g()
