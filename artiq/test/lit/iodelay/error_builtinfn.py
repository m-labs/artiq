# RUN: %python -m artiq.compiler.testbench.signature +diag +delay %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def f():
    x = 1
    # CHECK-L: ${LINE:+1}: error: call cannot be interleaved because an argument cannot be statically evaluated
    delay_mu(x)

def g():
    x = 1.0
    # CHECK-L: ${LINE:+1}: error: call cannot be interleaved
    delay(x)


