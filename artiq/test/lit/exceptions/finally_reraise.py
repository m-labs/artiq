# RUN: %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t
# REQUIRES: exceptions

x = 1

def doit():
    try:
        if x > 0:
            raise ZeroDivisionError
        r = 0
    finally:
        print('final')
    return r

try:
    doit()
except ZeroDivisionError:
    print('caught')

# CHECK-L: final
# CHECK-L: caught
