# RUN: %python -m artiq.compiler.testbench.signature +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def f():
    delay_mu(2)

def g():
    delay_mu(2)

x = f if True else g

def h():
    with interleave:
        f()
        # CHECK-L: ${LINE:+1}: fatal: it is not possible to interleave this function call within a 'with interleave:' statement because the compiler could not prove that the same function would always be called
        x()
