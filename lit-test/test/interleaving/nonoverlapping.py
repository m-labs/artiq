# RUN: %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def g():
    with parallel:
        with sequential:
            print("A", now_mu())
            delay_mu(2)
            #
            print("B", now_mu())
        with sequential:
            print("C", now_mu())
            delay_mu(2)
            #
            print("D", now_mu())
            delay_mu(2)
            #
            print("E", now_mu())

# CHECK-L: A 0
# CHECK-L: B 2
# CHECK-L: C 2
# CHECK-L: D 2
# CHECK-L: E 4
g()
