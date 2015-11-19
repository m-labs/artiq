# RUN: %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def g():
    with parallel:
        with sequential:
            print("A", now_mu())
            delay_mu(3)
            print("B", now_mu())
        with sequential:
            print("C", now_mu())
            delay_mu(2)
            print("D", now_mu())
            delay_mu(2)
            print("E", now_mu())

# CHECK-L: C 0
# CHECK-L: A 2
# CHECK-L: D 5
# CHECK-L: B 7
# CHECK-L: E 7
g()
