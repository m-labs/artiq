# RUN: %python -m artiq.compiler.testbench.signature +diag +delay %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def f(a):
    b = 1.0
    # CHECK-L: ${LINE:+3}: error: call cannot be interleaved
    # CHECK-L: ${LINE:+2}: note: this variable is not an argument of the innermost function
    # CHECK-L: ${LINE:-4}: note: only these arguments are in scope of analysis
    delay(b)

def g():
    # CHECK-L: ${LINE:+2}: error: call cannot be interleaved
    # CHECK-L: ${LINE:+1}: note: this operator is not supported as an argument for delay()
    delay(2.0**2)

def h():
    # CHECK-L: ${LINE:+2}: error: call cannot be interleaved
    # CHECK-L: ${LINE:+1}: note: this expression is not supported as an argument for delay_mu()
    delay_mu(1 if False else 2)

f(1)
