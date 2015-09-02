# RUN: %python -m artiq.compiler.testbench.signature +diag +delay %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def f():
    if True:
        # CHECK-L: ${LINE:+1}: error: only return statement at the end of the function can be interleaved
        return 1
    delay_mu(1)
