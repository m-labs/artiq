# RUN: %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t
# REQUIRES: exceptions

def doit():
    try:
        try:
            raise RuntimeError("Error")
        except ValueError:
            print("ValueError")
    finally:
        print("Cleanup")

try:
    doit()
except RuntimeError:
    print("Caught")

# CHECK-L: Cleanup
# CHECK-NEXT-L: Caught
