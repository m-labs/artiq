# RUN: %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t
# REQUIRES: exceptions

def f():
    try:
        1/0
    except ValueError:
        # CHECK-NOT-L: FAIL
        print("FAIL")

try:
    f()
except ZeroDivisionError:
    # CHECK-L: OK
    print("OK")
