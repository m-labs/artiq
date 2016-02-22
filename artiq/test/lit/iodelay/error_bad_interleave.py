# RUN: %python -m artiq.compiler.testbench.signature +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def f():
    with interleave:
        # CHECK-L: ${LINE:+1}: error: while statement cannot be interleaved
        while True:
            delay_mu(1)
