# RUN: %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def f(n):
    delay_mu(n)

def g():
    with interleave:
        with sequential:
            print("A", now_mu())
            f(2)
            #
            print("B", now_mu())
        with sequential:
            print("C", now_mu())
            f(2)
            #
            print("D", now_mu())
            f(2)
            #
            print("E", now_mu())

# CHECK-L: A 0
# CHECK-L: C 0
# CHECK-L: B 2
# CHECK-L: D 2
# CHECK-L: E 4
g()
