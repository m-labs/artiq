# RUN: %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def f():
    delay_mu(2)

def g():
    with interleave:
        f()
        delay_mu(2)
    print(now_mu())

# CHECK-L: 2
g()
