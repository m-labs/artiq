# RUN: %python -m artiq.compiler.testbench.signature +diag +delay %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def pulse(len):
    # "on"
    delay_mu(len)
    # "off"
    delay_mu(len)

def f():
    a = 100
    # CHECK-L: ${LINE:+1}: error: call cannot be interleaved
    pulse(a)
