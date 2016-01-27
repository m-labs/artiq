# RUN: %python -m artiq.compiler.testbench.signature +diag +delay %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def f():
    # CHECK-L: ${LINE:+1}: error: call cannot be interleaved
    delay(1.0**2)

def g():
    # CHECK-L: ${LINE:+1}: note: function called here
    f()
    f()
