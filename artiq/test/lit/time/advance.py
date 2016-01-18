# RUN: %python -m artiq.compiler.testbench.jit %s

assert now() == 0.0
delay(100.0)
assert now() == 100.0
at(12345.0)
assert now() == 12345.0

assert now_mu() == 12345000000
