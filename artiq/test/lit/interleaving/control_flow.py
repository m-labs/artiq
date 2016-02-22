# RUN: %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def f():
    with interleave:
        if True:
            print(1)
        else:
            print(2)
        while False:
            print(3)
            break
        delay_mu(1)
    print(4)

# CHECK-L: 1
# CHECK-L: 4
f()
