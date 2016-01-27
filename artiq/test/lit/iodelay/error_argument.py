# RUN: %python -m artiq.compiler.testbench.signature +diag +delay %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def f(x):
    delay_mu(x)

x = 1

def g():
    # CHECK-L: ${LINE:+2}: error: call cannot be interleaved because an argument cannot be statically evaluated
    # CHECK-L: ${LINE:+1}: note: this expression is not supported in the expression for argument 'x' that affects I/O delay
    f(x if True else x)
