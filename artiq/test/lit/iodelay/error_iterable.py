# RUN: %python -m artiq.compiler.testbench.signature +diag +delay %s >%t
# RUN: OutputCheck %s --file-to-check=%t

x = 1

def f():
    # CHECK-L: ${LINE:+2}: error: for statement cannot be interleaved because iteration count is indeterminate
    # CHECK-L: ${LINE:+1}: note: this expression is not supported in an iterable used in a for loop that is being interleaved
    for _ in range(x if True else x):
        delay_mu(10)
