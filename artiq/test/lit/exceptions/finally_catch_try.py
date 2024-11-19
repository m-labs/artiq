# RUN: %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t
# REQUIRES: exceptions

def doit():
    try:
        try:
            raise RuntimeError("Error")
        except ValueError:
            print("ValueError")
    except RuntimeError:
        print("Caught")
    finally:
        print("Cleanup")

doit()

# CHECK-L: Caught
# CHECK-NEXT-L: Cleanup
