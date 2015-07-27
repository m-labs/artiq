# RUN: %not %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t
# REQUIRES: exceptions

def f():
    try:
        1/0
    finally:
        print("f-fin")

# CHECK-L: f-fin
f()
