# RUN: %python -m artiq.compiler.testbench.jit %s

assert now_mu() == 0
delay_mu(100)
assert now_mu() == 100
at_mu(12345)
assert now_mu() == 12345
