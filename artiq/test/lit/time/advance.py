# RUN: %python -m artiq.compiler.testbench.jit %s
# REQUIRES: time

assert now_mu() == 0
delay(100.0)
assert now_mu() == 100000000
at_mu(12345000000)
assert now_mu() == 12345000000
