# RUN: %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t

with interleave:
    for x in range(10):
        delay_mu(1)
        print("a", x)
    with sequential:
        delay_mu(5)
        print("c")
    with sequential:
        delay_mu(3)
        print("b")

# CHECK-L: a 0
# CHECK-L: a 1
# CHECK-L: a 2
# CHECK-L: b
# CHECK-L: a 3
# CHECK-L: a 4
# CHECK-L: c
# CHECK-L: a 5
# CHECK-L: a 6
