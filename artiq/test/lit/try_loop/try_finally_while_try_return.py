# RUN: %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t
# REQUIRES: exceptions

def run():
    try:
        while True:
            try:
                print("try")
                func()
                return True
            except RuntimeError:
                print("except")
                return False
        print("unreachable")
    finally:
        print("finally")
    print("unreachable")
    return False


def func():
    pass

# CHECK-L: try
# CHECK-NOT-L: except
# CHECK-NOT-L: unreachable
# CHECK-L: finally
run()
