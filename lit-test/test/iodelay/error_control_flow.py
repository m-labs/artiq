# RUN: %python -m artiq.compiler.testbench.signature +diag +delay %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def f():
    # CHECK-L: ${LINE:+1}: error: while statement cannot be interleaved
    while True:
        delay_mu(1)

def g():
    # CHECK-L: ${LINE:+1}: error: if statement cannot be interleaved
    if True:
        delay_mu(1)

def h():
    # CHECK-L: ${LINE:+1}: error: if expression cannot be interleaved
    delay_mu(1) if True else delay_mu(2)

def i():
    # CHECK-L: ${LINE:+1}: error: try statement cannot be interleaved
    try:
        delay_mu(1)
    finally:
        pass
