# RUN: %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t
# REQUIRES: exceptions

def f():
    try:
        1/0
    except:
        print("f-except")
    finally:
        print("f-fin")
    print("f-out")

# CHECK-L: f-except
# CHECK-L: f-fin
# CHECK-L: f-out
f()
