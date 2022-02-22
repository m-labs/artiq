# RUN: %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t
# REQUIRES: exceptions

def run():
    loop = 0
    print("start")
    try:
        while True:
            print("loop")
            try:
                if loop == 0:
                    loop += 1
                    continue
                func()
                break
            except RuntimeError:
                print("except")
                return False
            finally:
                print("finally2")
        print("after-while")
    finally:
        print("finally1")
    print("exit")
    return True


def func():
    print("func")

# CHECK-L: start
# CHECK-NEXT-L: loop
# CHECK-NEXT-L: finally2
# CHECK-NEXT-L: loop
# CHECK-NEXT-L: func
# CHECK-NEXT-L: finally2
# CHECK-NEXT-L: after-while
# CHECK-NEXT-L: finally1
# CHECK-NEXT-L: exit

run()
