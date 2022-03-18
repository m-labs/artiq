# RUN: %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t
# REQUIRES: exceptions

def run():
    print("start")
    try:
        try:
            while True:
                print("loop")
                try:
                    print("try")
                    func()
                    print("unreachable")
                    return True
                except RuntimeError:
                    print("except1")
                    raise
            print("unreachable")
        finally:
            print("finally1")
        print("unreachable")
        return False
    except RuntimeError:
        print("except2")
        raise
    finally:
        print("finally2")
        return True


def func():
    raise RuntimeError("Test")

# CHECK-L: start
# CHECK-NEXT-L: loop
# CHECK-NEXT-L: try
# CHECK-NEXT-L: except1
# CHECK-NEXT-L: finally1
# CHECK-NEXT-L: except2
# CHECK-NEXT-L: finally2
run()
